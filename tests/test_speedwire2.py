"""Tests for the Speedwire V2 inverter adapter (device_speedwire2)."""

import logging

from pysma.device_speedwire2 import _AsyncSpeedwireSession
from pysma.sensor import Sensor


def _make_session() -> _AsyncSpeedwireSession:
    """Return a bare session without touching the network."""
    return _AsyncSpeedwireSession(
        host="192.0.2.1", password="0000", logger=logging.getLogger("test")
    )


class Test_speedwire2_discovery:
    """Discovery must not depend on the time of day / inverter producing."""

    def test_supported_channel_with_null_value_is_discovered(self) -> None:
        """A register answered with no value (asleep inverter) is still a
        supported sensor and must be discovered."""
        session = _make_session()
        grid_power = Sensor("grid_power", "grid_power", unit="W")

        # Inverter is asleep: the register is answered but decodes to None.
        session.handle_newvalue(grid_power, None, overwrite=True)

        assert "grid_power" in session.sensors
        assert session.sensors["grid_power"].value is None

    def test_null_does_not_clobber_known_value(self) -> None:
        """Once a real value is known, a later None must not erase it."""
        session = _make_session()
        grid_power = Sensor("grid_power", "grid_power", unit="W")

        session.handle_newvalue(grid_power, 1234, overwrite=True)
        session.handle_newvalue(grid_power, None, overwrite=True)

        assert session.sensors["grid_power"].value == 1234

    def test_value_populates_after_discovery_while_asleep(self) -> None:
        """A channel discovered while asleep must update once the inverter
        wakes -- this is the recovery that previously required a reload."""
        session = _make_session()
        grid_power = Sensor("grid_power", "grid_power", unit="W")

        session.handle_newvalue(grid_power, None, overwrite=True)  # night
        session.handle_newvalue(grid_power, 5000, overwrite=True)  # sunrise

        assert session.sensors["grid_power"].value == 5000

    def test_sessions_do_not_share_sensor_state(self) -> None:
        """Each session keeps its own sensors (no shared class-level dict)."""
        first = _make_session()
        second = _make_session()

        first.handle_newvalue(Sensor("grid_power", "grid_power", unit="W"), 1, True)

        assert "grid_power" in first.sensors
        assert "grid_power" not in second.sensors
