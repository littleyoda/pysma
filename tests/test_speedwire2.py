"""Tests for Speedwire V2 inverter adapter known_sensors accessor."""

import logging

from pysma.device_speedwire2 import SMAspeedwireINVV2, _AsyncSpeedwireSession
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
