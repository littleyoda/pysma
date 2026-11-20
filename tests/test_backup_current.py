"""Test discovery and decoding of Backup (Ongrid) phase currents."""

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from pysma.const_webconnect import GENERIC_SENSORS
from pysma.definitions_webconnect import sensor_map
from pysma.device_webconnect import SMAwebconnect
from pysma.sensor import Sensors

BACKUP_CURRENTS = (
    ("6100_40574600", "backup_current_l1"),
    ("6100_40574700", "backup_current_l2"),
    ("6100_40574800", "backup_current_l3"),
)


@pytest.mark.parametrize("key,name", BACKUP_CURRENTS)
@pytest.mark.parametrize(
    "raw,expected", [(12345, 12.345), (20000, 20.0), (0, 0.0), (None, None)]
)
def test_backup_current_decoding(key, name, raw, expected):
    """Decode milliamperes as amperes without turning unavailable into zero."""
    sensors = Sensors(sensor_map[GENERIC_SENSORS])
    sensor = sensors[name]
    assert sensor.key == key
    assert sensor.unit == "A"
    assert sensor.enabled
    sensor.extract_value({key: {"9": [{"val": raw}]}})
    assert sensor.value == expected


@pytest.mark.parametrize("available", [(), BACKUP_CURRENTS[:1], BACKUP_CURRENTS])
async def test_backup_current_discovery(available):
    """Expose only the backup phases reported by the inverter."""
    values = {key: {"9": [{"val": 1000}]} for key, _ in available}
    async with aiohttp.ClientSession() as session:
        sma = SMAwebconnect(session, "http://inverter.invalid", "pass")
        with patch.object(sma, "_read_all_sensors", new=AsyncMock(return_value=values)):
            sensors = await sma.get_sensors()
    assert {sensor.name for sensor in sensors} == {name for _, name in available}
