"""Test pysma init."""
import asyncio
import base64
import json
import logging

from aioresponses import aioresponses

from pysma.device_em import SMAspeedwireEM

_LOGGER = logging.getLogger(__name__)


class Test_SMAEM_class:
    """Test the SMA class."""

    async def looper(self, sma: SMAspeedwireEM) -> None:
        """Send fake packets from SunnyHomeManager2"""
        with open("tests/testdata/SunnyHomeManager2.json", "r") as file:
            data = json.load(file)
            data = base64.b64decode(data["packet"])
        for _ in range(1_000_000_000):
            await asyncio.sleep(0.6)
            sma.datagram_received(data, ("192.0.2.1", 4711))

    async def test_json_timeout_error(self, mock_aioresponse: aioresponses) -> None:
        """Basic Tests"""
        sma = SMAspeedwireEM()
        task = asyncio.create_task(self.looper(sma))
        await sma.new_session()
        device_info = await sma.device_info()
        print(device_info)
        for key in ["manufacturer", "name", "serial", "sw_version", "type"]:
            assert key in device_info
            assert (
                len(device_info[key]) > 0 if isinstance(device_info[key], str) else True
            )
            assert device_info[key] > 0 if isinstance(device_info[key], int) else True
        sensors = await sma.get_sensors()
        assert len(sensors) >= 17
        await sma.read(sensors)
        task.cancel()

    async def test_debug(self) -> None:
        """Checks the encoding for the debug-information."""
        sma = SMAspeedwireEM()
        with open("tests/testdata/SunnyHomeManager2.json", "r") as file:
            data = json.load(file)
            packet = base64.b64decode(data["packet"])
            sma.di.last_packet = packet
            sma.di.last_valid_packet = packet
            debug = await sma.get_debug()
            print(debug)
            assert debug["last_packet"] == debug["last_valid_packet"] == data["packet"]
