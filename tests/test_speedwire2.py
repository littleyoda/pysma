"""Tests for Speedwire V2 inverter adapter known_sensors accessor."""

import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest

from pysma.device_speedwire2 import SMAspeedwireINVV2, _AsyncSpeedwireSession
from pysma.exceptions import SmaConnectionException
from pysma.sensor import Sensor


def _make_session() -> _AsyncSpeedwireSession:
    """Return a bare session without touching the network."""
    return _AsyncSpeedwireSession(
        host="192.0.2.1", password="0000", logger=logging.getLogger("test")
    )


class Test_speedwire2_known_sensors:
    """The no-poll accessor used by consumers for runtime re-discovery."""

    def test_empty_without_session(self) -> None:
        dev = SMAspeedwireINVV2(host="192.0.2.1", group="user", password="0000")
        assert dev.known_sensors() == []

    def test_reflects_live_session_without_poll(self) -> None:
        dev = SMAspeedwireINVV2(host="192.0.2.1", group="user", password="0000")
        dev._session = _make_session()
        dev._session.handle_newvalue(
            Sensor("grid_power", "grid_power", unit="W"), 4200, True
        )

        keys = [s.key for s in dev.known_sensors()]
        assert "grid_power" in keys


async def test_udp_send_permission_error_is_connection_error() -> None:
    """A blocked UDP send must use the library's connection exception."""
    session = _make_session()
    session._protocol = Mock()
    session._protocol.request = AsyncMock(
        side_effect=PermissionError(1, "not permitted")
    )

    with patch.object(session, "_ensure_transport", new=AsyncMock()):
        with pytest.raises(SmaConnectionException) as exc_info:
            await session._send_receive("login2")

    assert isinstance(exc_info.value.__cause__, PermissionError)
    assert "192.0.2.1:9522" in str(exc_info.value)


async def test_discovery_reports_udp_permission_error_as_failed() -> None:
    """A blocked UDP socket must not abort the whole discovery scan."""
    device = SMAspeedwireINVV2(host="192.0.2.1", group="user", password="0000")

    with patch.object(
        _AsyncSpeedwireSession,
        "_ensure_transport",
        new=AsyncMock(side_effect=PermissionError(1, "not permitted")),
    ):
        result = await device.detect("192.0.2.1")

    assert len(result) == 1
    assert result[0].status == "failed"
    assert isinstance(result[0].exception, SmaConnectionException)
