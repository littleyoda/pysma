"""Test token expiry against a local HTTP server without mocking aiohttp internals."""

import logging
from collections import Counter
from types import SimpleNamespace

import aiohttp
import pytest
from aiohttp import web

from pysma.device_ennexos import SMAennexos
from pysma.exceptions import SmaAuthenticationException
from pysma.sensor import Sensor, Sensors


@pytest.fixture
async def inverter(aiohttp_server):
    """Provide an EnnexOS client and a server with configurable auth responses."""
    state = SimpleNamespace(
        calls=Counter(),
        expired=True,
        reject_retry=False,
        reject_login=False,
        body="Unauthorized",
        content_type="text/plain",
        live_status=200,
        invalid_json=False,
        login_status=200,
        authorization=[],
    )

    def unauthorized():
        return web.Response(
            status=401, text=state.body, content_type=state.content_type
        )

    async def respond(request):
        path = request.match_info["path"]
        state.calls[path] += 1
        if path == "token":
            if state.reject_login:
                return unauthorized()
            if state.login_status == 400:
                return web.json_response({"error": "invalid_request"}, status=400)
            return web.json_response({"access_token": "renewed-test-token"})
        if path == "measurements/live":
            state.authorization.append(request.headers.get("Authorization"))
            if state.expired or state.reject_retry:
                state.expired = False
                return unauthorized()
            if state.live_status != 200:
                return web.Response(status=state.live_status)
            if state.invalid_json:
                return web.Response(text="{", content_type="application/json")
            return web.json_response(
                [{"channelId": "Measurement.GridMs.TotW", "values": [{"value": 123}]}]
            )
        if path == "parameters/search":
            return web.json_response([{"values": []}])
        return web.json_response({})

    app = web.Application()
    app.router.add_route("*", "/api/v1/{path:.*}", respond)
    server = await aiohttp_server(app)
    async with aiohttp.ClientSession() as session:
        device = SMAennexos(session, str(server.make_url("")), "test-pass", "user")
        device._authorization_header = {"Authorization": "Bearer expired-test-token"}
        yield device, state


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        ("Unauthorized", "text/plain"),
        ('{"error": "expired"}', "application/json"),
        ("{", "application/json"),
    ],
)
async def test_expired_token_recovers_without_warning(
    inverter, body, content_type, caplog
):
    """A first 401 triggers one login/retry without premature error logging."""
    device, state = inverter
    state.body, state.content_type = body, content_type
    sensors = Sensors()
    sensors.add(Sensor("GridMs.TotW", "Power"))
    with caplog.at_level(logging.WARNING, logger="pysma.device_ennexos"):
        assert await device.read(sensors)
    assert sensors["Power"].value == 123
    assert not caplog.records
    assert state.calls["token"] == 1
    assert state.calls["measurements/live"] == 2
    assert state.authorization == [
        "Bearer expired-test-token",
        "Bearer renewed-test-token",
    ]


@pytest.mark.parametrize("failed_request", ["login", "retry"])
async def test_reauthentication_failure_is_propagated(inverter, failed_request):
    """A failed login or repeated 401 must escape the bounded retry."""
    device, state = inverter
    state.reject_login = failed_request == "login"
    state.reject_retry = failed_request == "retry"
    with pytest.raises(SmaAuthenticationException):
        await device.read(Sensors())
    assert state.calls["token"] == 1
    assert state.calls["measurements/live"] == (1 if failed_request == "login" else 2)


async def test_initial_login_rejection_is_propagated(inverter):
    """Initial authentication still fails for invalid credentials."""
    device, state = inverter
    state.reject_login = True
    with pytest.raises(SmaAuthenticationException):
        await device.new_session()


async def test_invalid_json_with_success_status_remains_an_error(inverter, caplog):
    """The exception for 401 must not silence malformed successful responses."""
    device, state = inverter
    state.expired = False
    state.invalid_json = True
    with caplog.at_level(logging.ERROR, logger="pysma.device_ennexos"):
        await device._jsonrequest(device._url + "/api/v1/measurements/live", {})
    assert "did not return a valid json. Code 200" in caplog.text


async def test_bad_request_remains_an_error(inverter, caplog):
    """HTTP 400 retains its existing logging and authentication exception."""
    device, state = inverter
    state.login_status = 400
    with caplog.at_level(logging.ERROR, logger="pysma.device_ennexos"):
        with pytest.raises(SmaAuthenticationException):
            await device.new_session()
    assert "Error 400" in caplog.text


async def test_server_error_remains_a_warning(inverter, caplog):
    """Other HTTP errors keep their existing warning."""
    device, state = inverter
    state.expired = False
    state.live_status = 500
    with caplog.at_level(logging.WARNING, logger="pysma.device_ennexos"):
        await device._jsonrequest(device._url + "/api/v1/measurements/live", {})
    assert "HTTP-Error 500" in caplog.text
