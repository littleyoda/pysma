"""Interface for SMA ennoxOS based devices.

e.g. Tripower X and maybe EV Charger.
"""

import asyncio
import copy
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from aiohttp import ClientSession, ClientTimeout, client_exceptions, hdrs

from .const import SMATagList
from .const_webconnect import DEFAULT_TIMEOUT
from .definitions_ennexos import getSensorForDevice
from .device import Device, DeviceInformation, DiscoveryInformation
from .exceptions import (
    SmaAuthenticationException,
    SmaConnectionException,
    SmaReadException,
)
from .sensor import Sensor, Sensor_Range, Sensors

_LOGGER = logging.getLogger(__name__)


@dataclass
class EnnexosDebug:
    parameters: dict[str, Any] = field(default_factory=dict)
    parameters_raw: dict[str, Any] = field(default_factory=dict)
    measurements: dict[str, Any] = field(default_factory=dict)
    measurements_raw: dict[str, Any] = field(default_factory=dict)
    last_notfound: dict[str, list] = field(default_factory=dict)
    profilemissing: dict[str, list] = field(default_factory=dict)
    plantInfo: dict[str, Any] = field(default_factory=dict)
    devInfo: dict[str, Any] = field(default_factory=dict)


class SMAennexos(Device):
    """Class to connect to the ennexos based SMA inverters."""

    # pylint: disable=too-many-instance-attributes
    _debug: EnnexosDebug = EnnexosDebug()

    _aio_session: ClientSession
    _new_session_data: Optional[dict[str, Any]]
    _url: str
    _authorization_header: dict[str, str]
    _componentId = "IGULD:SELF"
    _device_list: Dict[str, DeviceInformation] = {}

    def __init__(
        self,
        session: ClientSession,
        url: str,
        password: str | None,
        group: str | None,
    ):
        """Init SMA connection.

        Args:
            session (ClientSession): aiohttp client session
            url (str): Url or IP address of device
            password (str, optional): Password to use during login.
            group (str, optional): Username to use during login.

        """
        self._url = url.rstrip("/")
        if not url.startswith("http"):
            self._url = "https://" + self._url
        self._new_session_data = {"user": group, "pass": password}
        self._aio_session = session

    async def _jsonrequest(
        self, url: str, parameters: Dict[str, Any], method: str = hdrs.METH_POST
    ) -> Any:
        """Request json data for requests.

        Args:
            url (str): URL to do request to
            parameters (Dict[str, Any]): parameters
            method (str): Post or Get-Request

        Raises:
            SmaConnectionException: Connection to device failed
            SmaAuthenticationException: Authentication failed

        Returns:
            dict: json returned by device
        """
        try:
            async with self._aio_session.request(
                method, url, timeout=ClientTimeout(total=DEFAULT_TIMEOUT), **parameters
            ) as res:
                if res.status == 200:
                    res = await res.json()
                    return res
                elif res.status == 401 or res.status == 400:
                    raise SmaAuthenticationException("Token failed!")
                else:
                    _LOGGER.warning("HTTP-Error %d for %s", res.status, url)
                    return {}
        except SmaAuthenticationException as e:
            raise e
        except (client_exceptions.ContentTypeError, json.decoder.JSONDecodeError):
            _LOGGER.warning("Request to %s did not return a valid json.", url)
        except client_exceptions.ServerDisconnectedError as exc:
            raise SmaConnectionException(
                f"Server at {self._url} disconnected."
            ) from exc
        except (
            client_exceptions.ClientError,
            asyncio.exceptions.TimeoutError,
        ) as exc:
            raise SmaConnectionException(
                f"Could not connect to SMA at {self._url}: {exc}"
            ) from exc
        return {}

    # @override
    async def new_session(self) -> bool:
        """Establish a new session.

        Returns:
            bool: authentication successful
        """
        if self._new_session_data is None:
            _LOGGER.error("User & Pwd not set!")
            return False
        loginurl = self._url + "/api/v1/token"
        postdata = {
            "data": {
                "grant_type": "password",
                "username": self._new_session_data["user"],
                "password": self._new_session_data["pass"],
            }
        }
        ret = await self._jsonrequest(loginurl, postdata)
        if "access_token" not in ret:
            raise SmaAuthenticationException("Login failed!")
        self._authorization_header = {
            "Authorization": "Bearer " + ret["access_token"],
            "Content-Type": "application/json",
        }
        _LOGGER.debug("Login successful")

        for u in [
            "/api/v1/plants/Plant:1",
            "/api/v1/plants/Plant:1/devices",
            "/api/v1/featuretoggles",
        ]:
            url = self._url + u
            ret = await self._jsonrequest(
                url, {"headers": self._authorization_header}, hdrs.METH_GET
            )
            if isinstance(ret, dict):
                ret.pop("_links", None)
            if isinstance(ret, list):
                for i in ret:
                    if isinstance(i, dict):
                        i.pop("_links", None)

            self._debug.plantInfo[u.split("/")[-1]] = ret

        return True

    async def _get_parameter(self, componentId: str) -> Dict[str, Dict[str, Any]]:
        """Get all parameters from the device.

        Returns:
            Dict: Return a dict with all parameters

        """
        liveurl = self._url + "/api/v1/parameters/search"
        postdata = {
            "data": '{"queryItems":[{"componentId":"' + componentId + '"}]}',
            "headers": self._authorization_header,
        }
        ret = await self._jsonrequest(liveurl, postdata)
        data = await self._prepare_parameter(ret, componentId)
        return data

    async def _prepare_parameter(
        self, ret: Any, componentId: str
    ) -> Dict[str, Dict[str, Any]]:
        data: Dict[str, Dict[str, Any]] = {}
        if len(ret) != 1:
            _LOGGER.warning(
                "Uncommon length of array in parameters request: %d", len(ret)
            )

        if len(ret) > 0:
            for d in ret[0]["values"]:
                dname = d["channelId"].replace("Parameter.", "").replace("[]", "")
                if "value" in d:
                    v = d["value"]
                    sensor_range = Sensor_Range("", [], d["editable"])
                    if "min" in d and "max" in d:
                        sensor_range = Sensor_Range(
                            "min/max", [d["min"], d["max"]], d["editable"]
                        )
                    if "possibleValues" in d:
                        sensor_range = Sensor_Range(
                            "selection", d["possibleValues"], d["editable"]
                        )

                    data[dname] = {
                        "name": dname,
                        "value": v,
                        "origname": d["channelId"],
                        "range": sensor_range,
                    }

                elif "values" in d:
                    # Split Value-Arrays
                    for idx in range(0, len(d["values"])):
                        v = d["values"][idx]
                        idxname = dname + "." + str(idx + 1)
                        data[idxname] = {
                            "name": idxname,
                            "value": v,
                            "origname": d["channelId"],
                        }
                else:
                    # Value current not available // night?
                    pass
        self._debug.parameters_raw[componentId] = ret
        self._debug.parameters[componentId] = data
        return data

    async def _get_all_readings(self, deviceID: str) -> Dict[str, Dict[str, Any]]:
        readings = await self._get_livedata(deviceID)
        readings.update(await self._get_parameter(deviceID))
        return readings

    async def _get_livedata(self, componentId: str) -> Dict[str, Dict[str, Any]]:
        """Get the sensors reading from the device.

        Returns:
            Dict: Return a dict with all measurements

        """
        liveurl = self._url + "/api/v1/measurements/live"
        postdata = {
            "data": '[{"componentId":"' + componentId + '"}]',
            "headers": self._authorization_header,
        }
        ret = await self._jsonrequest(liveurl, postdata)
        out = await self._prepare_livedata(ret, componentId)
        return out

    async def _prepare_livedata(
        self, ret: Any, componentId: str
    ) -> Dict[str, Dict[str, Any]]:
        """Convert the raw data from the inverter to a dict"""
        data: Dict[str, Any] = {}
        for d in ret:
            dname = d["channelId"].replace("Measurement.", "").replace("[]", "")
            if "value" in d["values"][0]:
                v = d["values"][0]["value"]
                if self._isfloat(v):
                    v = round(v, 2)
                data[dname] = {"name": dname, "value": v, "origname": d["channelId"]}
            elif "values" in d["values"][0]:
                # Split Value-Arrays
                for idx in range(0, len(d["values"][0]["values"])):
                    v = d["values"][0]["values"][idx]
                    if self._isfloat(v):
                        v = round(v, 2)
                    idxname = dname + "." + str(idx + 1)
                    data[idxname] = {
                        "name": idxname,
                        "value": v,
                        "origname": d["channelId"],
                    }
            else:
                # Value current not available // night?
                pass
        self._debug.measurements_raw[componentId] = ret
        self._debug.measurements[componentId] = data
        return data

    # @override
    async def get_sensors(self, deviceID: str | None = None) -> Sensors:
        """Get the sensors that are present on the device.

        Returns:
            Sensors: Sensors object containing Sensor objects
        """
        if not self._device_list:
            raise SmaReadException("device_info() not called!")
        deviceID = self.deviceIDFallback(deviceID)

        # Mark sure this function get called at least once
        ret = await self._get_all_readings(deviceID)
        _LOGGER.debug("Found Sensors for %s: %d", deviceID, len(ret))
        profile = await self._get_sensor_profile(deviceID)
        return profile

    async def _get_sensor_profile(self, deviceID: str) -> Sensors:
        device_sensors = Sensors()

        # Search for matiching profile
        dev = self._device_list[deviceID]
        productTagId = int(dev.additional.get("productTagId", 0))
        profile = getSensorForDevice(productTagId)
        if not profile:
            _LOGGER.warning(
                f"Unknown Device: {productTagId} N:{dev.name} T:{dev.type} ID:{deviceID}"
            )
            return device_sensors
        expected_sensors, unknown = profile
        if len(unknown) > 0:
            _LOGGER.debug(f"Missing Sensors in Profile {productTagId}: {unknown}")
            self._debug.profilemissing[deviceID] = unknown
        # Add Sensors from profile
        for s in expected_sensors:
            if s.name:
                device_sensors.add(copy.copy(s))
        return device_sensors

    async def close_session(self) -> None:
        """Closes the session."""

    def _isfloat(self, num: Any) -> bool:
        """Test if num is a float.

            Tests for type float or a string with a dot is is float

        Args:
            num: number to check

        Returns:
            bool: true, if num is from type float or a string with a dot
        """
        if isinstance(num, float):
            return True
        if isinstance(num, int):
            return False
        if not isinstance(num, str):
            raise TypeError("Value is not a string, float or int!")
        if "." not in num:
            return False
        try:
            float(num)
            return True
        except ValueError:
            return False

    def deviceIDFallback(self, deviceID: str | None) -> str:
        if not deviceID:
            return self._componentId
        return deviceID

    # @override
    async def read(self, sensors: Sensors, deviceID: str | None = None) -> bool:
        """Read a set of keys.

        Args:
            sensors (Sensors): Sensors object containing Sensor objects to read

        Returns:
            bool: reading was successful
        """
        notfound = []
        deviceID = self.deviceIDFallback(deviceID)
        data = None
        try:
            data = await self._get_all_readings(deviceID)
        except SmaAuthenticationException:
            # Relogin
            _LOGGER.debug("Re-login .. Starting new Session")
            await self.new_session()
            data = await self._get_all_readings(deviceID)
        for sen in sensors:
            if sen.enabled:
                if sen.key in data:
                    value = data[sen.key]["value"]
                    if sen.mapper:
                        sen.mapped_value = sen.mapper.get(value, str(value))
                    if sen.factor and sen.factor != 1:
                        value = round(value / sen.factor, 4)
                    sen.value = value
                    if "range" in data[sen.key]:
                        sen.range = data[sen.key]["range"]
                    continue
                notfound.append(f"{sen.name} [{sen.key}]")

        if deviceID not in self._debug.last_notfound:
            self._debug.last_notfound[deviceID] = []

        notfound = [x for x in notfound if x not in self._debug.last_notfound[deviceID]]
        if len(notfound) > 0:
            _LOGGER.info(
                "No values for sensors: %s",
                ",".join(notfound),
            )
            self._debug.last_notfound[deviceID].extend(notfound)
        return True

    # @override
    async def device_info(self) -> dict:
        """Read device info and return the results.

        Returns:
            dict: dict containing serial, name, type, manufacturer and sw_version
        """
        data = await self.device_list()
        if self._componentId in data:
            return data[self._componentId].asDict()
        else:
            return {}

    # @override
    async def device_list(self) -> dict[str, DeviceInformation]:

        devices = await self._jsonrequest(
            self._url + "/api/v1/plants/Plant:1/devices",
            {"headers": self._authorization_header},
            hdrs.METH_GET,
        )
        deviceID = {"IGULD:SELF"}
        for d in devices:
            deviceID.add(d["deviceId"])
        self._device_list = {}
        for d in deviceID:
            di = await self._device_info_by_componentId(d)
            if di:
                self._device_list[di.id] = di

        # TO DO move to device info by commpeontID TO DO
        # Adding Device-Placeholder for the whole plant
        pi = self._debug.plantInfo["Plant:1"]
        serial = "P" + self._device_list["IGULD:SELF"].serial
        self._device_list["Plant:1"] = DeviceInformation(
            "Plant:1", serial, pi["name"], pi["plantId"], "SMA", ""
        )
        self._device_list["Plant:1"].additional["productTagId"] = -47114711
        return self._device_list

    async def _device_info_by_componentId(
        self, componentId: str
    ) -> DeviceInformation | None:
        url = self._url + "/api/v1/plants/Plant:1/devices/" + componentId
        devInfo = await self._jsonrequest(
            url, {"headers": self._authorization_header}, hdrs.METH_GET
        )
        self._debug.devInfo[componentId] = devInfo
        if not devInfo:
            return None
        di = DeviceInformation(
            componentId,
            devInfo["serial"],
            devInfo["product"],
            devInfo["name"],
            devInfo["vendor"],
            devInfo["firmwareVersion"],
        )
        para = await self._get_parameter(componentId)
        di.parameterCount = len(para)
        data = await self._get_livedata(componentId)
        di.measurementsCount = len(data)
        for key, value in devInfo.items():
            if key in [
                "serial",
                "product",
                "name",
                "vendor",
                "firmwareVersion",
                "_links",
            ]:
                continue
            if type(value) not in [str, int, float]:
                continue
            di.additional[key] = value
        return di

    # @override
    async def get_debug(self) -> Dict:
        """Returns all Debug Information."""
        x = asdict(self._debug)
        x["device_list"] = self._device_list
        return x

    # @override
    async def detect(self, ip: str) -> list[DiscoveryInformation]:
        """Tries to detect a ennexos-based Device on this ip-address."""
        rets = []
        for prefix in ["https", "http"]:
            di = DiscoveryInformation()
            rets.append(di)
            url = f"{prefix}://{ip}/api/v1/system/info"
            di.tested_endpoints = url
            di.remark = prefix
            try:
                dev = await self._jsonrequest(url, {}, hdrs.METH_GET)
                if "productFriendlyNameTagId" in dev:
                    fallback = "Unknown: " + str(dev["productFriendlyNameTagId"])
                    di.device = SMATagList.get(
                        dev["productFriendlyNameTagId"], fallback
                    )
                    di.status = "found"
                    break
                di.status = "failed"
                di.exception = None
            except Exception as e:  # pylint: disable=broad-exception-caught
                di.status = "failed"
                di.exception = e
        return rets

    # @override
    def set_options(self, options: Dict[str, Any]) -> None:
        """Set low-level options."""
        for key, value in options.items():
            if key == "componentId":
                print(f"Option {key}: {self._componentId} => {value}")
                self._componentId = value
            else:
                _LOGGER.error("Unknown Options: %s %s", key, value)

    async def _get_timestamp(self) -> str:
        """Returns the time in a format as required by the put instruction."""
        return (
            f"{datetime.now(tz=UTC).isoformat(timespec='milliseconds').split('+')[0]}Z"
        )

    # @override
    async def set_parameter(
        self, sensor: Sensor, value: int, deviceID: str | None = None
    ) -> None:
        """SetParameters."""
        if deviceID not in self._device_list:
            raise RuntimeError("DeviceID %s unknown.", deviceID)
        timestamp = await self._get_timestamp()
        parameters = await self._get_parameter(deviceID)
        channelName = parameters[sensor.key]["origname"]
        requestData = f'{{"values":[{{"channelId":"{channelName}","timestamp":"{timestamp}","value":"{value}"}}]}}'
        putdata = {
            "data": requestData,
            "headers": self._authorization_header,
        }
        url = self._url + "/api/v1/parameters/" + deviceID
        dev = await self._jsonrequest(url, putdata, hdrs.METH_PUT)  # noqa: F841
