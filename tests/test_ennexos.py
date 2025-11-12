"""Test pysma init."""
import asyncio
import json
import logging
from unittest.mock import patch

import aiohttp
import pytest

from pysma.device_ennexos import SMAennexos
from pysma.exceptions import SmaAuthenticationException, SmaConnectionException

_LOGGER = logging.getLogger(__name__)


class Test_SMA_class:
    """Test the SMA class."""

    def loadJson(self, filename):
        with open("tests/testdata/" + filename, "r") as file:
            data = json.load(file)
        return data

    async def test_json_timeout_error(self, mock_aioresponse):
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

    async def test_json_serverdisconnected_error(self, mock_aioresponse):
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

    async def test_json_401(self, mock_aioresponse):
        """Test request_json with a SmaConnectionException from TimeoutError."""
        mock_aioresponse.post("/dummy-url", status=401)
        session = aiohttp.ClientSession()
        sma = SMAennexos(session, "localhost", "pass", "user")
        with pytest.raises(SmaAuthenticationException):
            await sma._jsonrequest("/dummy-url", {})
        await session.close()

    @patch("pysma.device_ennexos._LOGGER.warning")
    async def test_json_json(self, mock_warn, mock_aioresponse):
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

    async def test_newsession_pos(self, mock_aioresponse):
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

    async def test_known_device(self, mock_aioresponse):
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

    async def test_unknown_device(self, mock_aioresponse):
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
