"""Test pysma init."""
import asyncio
import json
import logging
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from pysma.device_ennexos import SMAennexos
from pysma.exceptions import SmaAuthenticationException, SmaConnectionException
from pysma.sensor import Sensors

from . import mock_aioresponse  # noqa: F401

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    ("expires_in", "expected_delay"), [(None, 3240), (120, 108), (0, 3240)]
)
async def test_token_refresh_schedule(expires_in, expected_delay):
    """A successful refresh replaces the token without reloading plant data."""
    async with aiohttp.ClientSession() as session:
        sma = SMAennexos(session, "localhost", "pass", "user")
        tokens = iter(("first", "second"))

        async def request(url, parameters, method="POST"):
            if url.endswith("/api/v1/token"):
                response = {"access_token": next(tokens)}
                if expires_in is not None:
                    response["expires_in"] = expires_in
                return response
            return {}

        with patch.object(sma, "_jsonrequest", side_effect=request) as mock_request:
            assert await sma.new_session()
            first_handle = sma._token_refresh_handle
            assert first_handle is not None
            assert (
                abs(
                    first_handle.when()
                    - asyncio.get_running_loop().time()
                    - expected_delay
                )
                < 1
            )

            first_handle.cancel()
            sma._start_token_refresh()
            assert sma._token_refresh_task is not None
            await sma._token_refresh_task

            assert sma._authorization_header["Authorization"] == "Bearer second"
            assert sma._token_refresh_handle is not first_handle
            assert sma._token_refresh_handle is not None
            assert mock_request.call_count == 5  # Two tokens, three initial reads
            refresh_handle = sma._token_refresh_handle
            await sma.close_session()
            assert refresh_handle.cancelled()
            sma._start_token_refresh()
            assert sma._token_refresh_task is None


async def test_token_refresh_retries_after_failure():
    """A failed background login keeps the old token and schedules a retry."""
    async with aiohttp.ClientSession() as session:
        sma = SMAennexos(session, "localhost", "pass", "user")
        attempts = 0

        async def request(url, parameters, method="POST"):
            nonlocal attempts
            if url.endswith("/api/v1/token"):
                attempts += 1
                if attempts == 2:
                    raise SmaConnectionException("offline")
                return {"access_token": "first"}
            return {}

        with patch.object(sma, "_jsonrequest", side_effect=request):
            await sma.new_session()
            sma._token_refresh_handle.cancel()
            sma._start_token_refresh()
            assert sma._token_refresh_task is not None
            await sma._token_refresh_task

            assert attempts == 2
            assert sma._authorization_header["Authorization"] == "Bearer first"
            assert sma._token_refresh_handle is not None
            assert (
                abs(
                    sma._token_refresh_handle.when()
                    - asyncio.get_running_loop().time()
                    - 60
                )
                < 1
            )
            await sma.close_session()


async def test_close_session_cancels_in_flight_refresh():
    """Closing during a token request prevents later refreshes."""
    async with aiohttp.ClientSession() as session:
        sma = SMAennexos(session, "localhost", "pass", "user")
        refresh_started = asyncio.Event()
        attempts = 0

        async def request(url, parameters, method="POST"):
            nonlocal attempts
            if url.endswith("/api/v1/token"):
                attempts += 1
                if attempts == 2:
                    refresh_started.set()
                    await asyncio.Event().wait()
                return {"access_token": "first"}
            return {}

        with patch.object(sma, "_jsonrequest", side_effect=request):
            await sma.new_session()
            sma._token_refresh_handle.cancel()
            sma._start_token_refresh()
            await asyncio.wait_for(refresh_started.wait(), 1)
            await sma.close_session()
            assert sma._token_refresh_task is None
            assert sma._token_refresh_handle is None


async def test_read_still_reauthenticates_on_401():
    """An unexpectedly invalid token still triggers the existing fallback."""
    async with aiohttp.ClientSession() as session:
        sma = SMAennexos(session, "localhost", "pass", "user")
        with patch.object(
            sma,
            "_get_all_readings",
            new=AsyncMock(side_effect=[SmaAuthenticationException(), {}]),
        ) as readings, patch.object(
            sma, "new_session", new=AsyncMock(return_value=True)
        ) as login:
            assert await sma.read(Sensors())
            assert readings.await_count == 2
            login.assert_awaited_once()


class Test_SMA_class:
    """Test the SMA class."""

    def loadJson(self, filename):
        with open("tests/testdata/" + filename, "r") as file:
            data = json.load(file)
        return data

    async def test_json_timeout_error(self, mock_aioresponse):  # noqa: F811
        """Test request_json with a SmaConnectionException from TimeoutError."""
        mock_aioresponse.post(
            "/dummy-url",
            exception=asyncio.TimeoutError("mocked error"),
        )
        session = aiohttp.ClientSession()
        sma = SMAennexos(session, "localhost", "pass", "user")
        with pytest.raises(SmaConnectionException):
            await sma._jsonrequest("/dummy-url", {})
        await session.close()

    async def test_json_serverdisconnected_error(self, mock_aioresponse):  # noqa: F811
        """Test request_json with a SmaConnectionException from TimeoutError."""
        mock_aioresponse.post(
            "/dummy-url",
            exception=aiohttp.client_exceptions.ServerDisconnectedError("mocked error"),
        )
        session = aiohttp.ClientSession()
        sma = SMAennexos(session, "localhost", "pass", "user")
        with pytest.raises(SmaConnectionException):
            await sma._jsonrequest("/dummy-url", {})
        await session.close()

    async def test_json_401(self, mock_aioresponse):  # noqa: F811
        """Test request_json with a SmaConnectionException from TimeoutError."""
        mock_aioresponse.post("/dummy-url", status=401)
        session = aiohttp.ClientSession()
        sma = SMAennexos(session, "localhost", "pass", "user")
        with pytest.raises(SmaAuthenticationException):
            await sma._jsonrequest("/dummy-url", {})
        await session.close()

    @patch("pysma.device_ennexos._LOGGER.warning")
    async def test_json_json(self, mock_warn, mock_aioresponse):  # noqa: F811
        """Test request_json with a SmaConnectionException from TimeoutError."""
        mock_aioresponse.post("/dummy-url", body="no-valid-json")
        session = aiohttp.ClientSession()
        sma = SMAennexos(session, "localhost", "pass", "user")
        await sma._jsonrequest("/dummy-url", {})
        await session.close()
        # assert mock_warn.call_count == 1

    async def test_newsession_neg(self, mock_aioresponse):  # noqa: F811
        mock_aioresponse.post("https://localhost/api/v1/token", payload={})
        session = aiohttp.ClientSession()
        sma = SMAennexos(session, "localhost", "pass", "user")
        with pytest.raises(SmaAuthenticationException):
            await sma.new_session()
        await session.close()

    async def test_newsession_pos(self, mock_aioresponse):  # noqa: F811
        mock_aioresponse.post(
            "https://localhost/api/v1/token", payload={"access_token": "sample"}
        )
        mock_aioresponse.get(
            "https://localhost/api/v1/plants/Plant:1", payload="", repeat=True
        )
        mock_aioresponse.get(
            "https://localhost/api/v1/plants/Plant:1/devices", payload="", repeat=True
        )
        session = aiohttp.ClientSession()
        sma = SMAennexos(session, "localhost", "pass", "user")
        await sma.new_session()
        await session.close()

    async def test_known_device(self, mock_aioresponse):  # noqa: F811
        """The the Case if it is a known"""
        mock_aioresponse.post(
            "https://localhost/api/v1/token", payload={"access_token": "sample"}
        )
        mock_aioresponse.get(
            "https://localhost/api/v1/plants/Plant:1/devices/IGULD:SELF",
            payload=self.loadJson("TripowerX15-deviceinfo.json"),
        )
        mock_aioresponse.post(
            "https://localhost/api/v1/parameters/search",
            payload=self.loadJson("TripowerX15-parameters.json"),
            repeat=True,
        )
        mock_aioresponse.post(
            "https://localhost/api/v1/measurements/live",
            payload=self.loadJson("TripowerX15-measurements.json"),
            repeat=True,
        )
        mock_aioresponse.get(
            "https://localhost/api/v1/plants/Plant:1",
            payload=self.loadJson("TripowerX15-plant1.json"),
            repeat=True,
        )
        mock_aioresponse.get(
            "https://localhost/api/v1/plants/Plant:1/devices",
            payload=self.loadJson("TripowerX15-plant1-devices.json"),
            repeat=True,
        )
        session = aiohttp.ClientSession()
        sma = SMAennexos(session, "localhost", "pass", "user")
        await sma.new_session()

        device_info = await sma.device_info()
        assert isinstance(device_info, dict)
        for key in ["manufacturer", "name", "serial", "sw_version", "type"]:
            assert key in device_info
            assert len(device_info[key]) > 0

        sensors = await sma.get_sensors()
        assert len(sensors) >= 36

        ret = await sma.read(sensors)
        assert ret is True

        await sma.get_debug()
        await session.close()

    async def test_unknown_device(self, mock_aioresponse):  # noqa: F811
        """Test the case if a unknown device is detected"""
        mock_aioresponse.post(
            "https://localhost/api/v1/token", payload={"access_token": "sample"}
        )
        mock_aioresponse.get(
            "https://localhost/api/v1/plants/Plant:1/devices/IGULD:SELF",
            payload=self.changeExistingDeviceInfo(
                "TripowerX15-deviceinfo.json",
                {
                    "productTagId": 9999999,
                    "product": "Unknown",
                    "vendor": "SomeoneElse",
                },
            ),
        )
        mock_aioresponse.post(
            "https://localhost/api/v1/parameters/search",
            payload=self.loadJson("TripowerX15-parameters.json"),
            repeat=True,
        )
        mock_aioresponse.post(
            "https://localhost/api/v1/measurements/live",
            payload=self.loadJson("TripowerX15-measurements.json"),
            repeat=True,
        )
        mock_aioresponse.get(
            "https://localhost/api/v1/plants/Plant:1",
            payload=self.changeExistingDeviceInfo(
                "TripowerX15-plant1.json",
                {"product": "Unknown", "vendor": "SomeoneElse"},
            ),
            # payload=self.loadJson("TripowerX15-plant1.json"),
            repeat=True,
        )
        mock_aioresponse.get(
            "https://localhost/api/v1/plants/Plant:1/devices",
            payload=self.changeExistingDeviceInfo(
                "TripowerX15-plant1-devices.json",
                {"product": "Unknown", "vendor": "SomeoneElse"},
            ),
            #            payload= self.loadJson("TripowerX15-plant1-devices.json"),
            repeat=True,
        )
        session = aiohttp.ClientSession()
        sma = SMAennexos(session, "localhost", "pass", "user")
        await sma.new_session()

        device_info = await sma.device_info()
        assert isinstance(device_info, dict)
        for key in ["manufacturer", "name", "serial", "sw_version", "type"]:
            assert key in device_info
            assert len(device_info[key]) > 0

        # No Sensors should be exported
        sensors = await sma.get_sensors()
        assert len(sensors) == 0

        ret = await sma.read(sensors)
        assert ret is True

        await sma.get_debug()
        await session.close()

    async def test_isfloat(self):
        assert SMAennexos._isfloat(None, "9.44")
        assert not SMAennexos._isfloat(None, "9")
        assert not SMAennexos._isfloat(None, "not a number")

    def change(self, data, replace: dict[str:str]):
        if isinstance(data, dict):
            for v in replace.items():
                print(v)
                data[v[0]] = v[1]

        if isinstance(data, list):
            for v in data:
                self.change(v, replace)
        return data

    def changeExistingDeviceInfo(self, filename: str, replace: dict[str:str]):
        data = self.loadJson(filename)
        data = self.change(data, replace)
        print(data)
        return data

    # async def test_evcharger_device(self, mock_aioresponse):
    #     mock_aioresponse.post(
    #         f"https://localhost/api/v1/token",
    #         payload={ "access_token": "sample"}
    #     )
    #     mock_aioresponse.get(
    #         f"https://localhost/api/v1/plants/Plant:1/devices/IGULD:SELF",
    #         payload= self.changeExistingDeviceInfo("TripowerX15-deviceinfo.json", {"product": "SMA EV Charger "})
    #     )
    #     mock_aioresponse.post(
    #         "https://localhost/api/v1/parameters/search",
    #         payload= [ {"values" : []} ],
    #         repeat=True
    #     )
    #     mock_aioresponse.post(
    #         "https://localhost/api/v1/measurements/live",
    #         payload= self.loadJson("EVCharger-measurements.json"),
    #         repeat = True
    #     )
    #     session = aiohttp.ClientSession()
    #     sma = SMAennexos(session, "localhost", "pass", "user")
    #     await sma.new_session()

    #     device_info = await sma.device_info()
    #     assert isinstance(device_info, dict)
    #     for key in ["manufacturer", "name", "serial", "sw_version", "type" ]:
    #         assert key in device_info
    #         assert len(device_info[key]) > 0

    #     # No Sensors should be exported
    #     sensors = await sma.get_sensors()
    #     # for i in sensors:
    #     #     print(i)
    #     assert len(sensors) == 13

    #     ret = await sma.read(sensors)
    #     assert ret == True
    #     # for s in sensors:
    #     #     print(f"{s.key} {s.value} {s.unit} {s.mapped_value if s.mapped_value else '' }")

    #     debug = await sma.get_debug()
    #     await session.close()
