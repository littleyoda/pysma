"""SMA WebConnect library for Python.

See: http://www.sma.de/en/products/monitoring-control/webconnect.html

Source: http://www.github.com/kellerza/pysma
"""

import asyncio
import copy
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

import jmespath  # type: ignore
from aiohttp import ClientSession, ClientTimeout, client_exceptions, hdrs

from . import definitions_webconnect
from .const_webconnect import (
    DEFAULT_LANG,
    DEFAULT_TIMEOUT,
    DEVICE_INFO,
    ENERGY_METER_VIA_INVERTER,
    FALLBACK_DEVICE_INFO,
    GENERIC_SENSORS,
    OPTIMIZERS_VIA_INVERTER,
    URL_ALL_PARAMS,
    URL_ALL_VALUES,
    URL_DASH_LOGGER,
    URL_DASH_VALUES,
    URL_LOGGER,
    URL_LOGIN,
    URL_LOGOUT,
    URL_SETPARAMETER,
    URL_VALUES,
    USERS,
)
from .device import Device, DeviceInformation, DiscoveryInformation
from .exceptions import (
    SmaAuthenticationException,
    SmaConnectionException,
    SmaReadException,
)
from .helpers import version_int_to_string
from .sensor import Sensor, Sensors

_LOGGER = logging.getLogger(__name__)


@dataclass
class Debug_information_webconnect:
    """Struct to store debug Information"""

    full_json: dict | None = None
    last_json: dict | None = None
    device_info: DeviceInformation | None = None
    all_values: dict | None = None
    all_params: dict | None = None


class SMAwebconnect(Device):
    """Class to connect to the SMA webconnect module and read parameters."""

    # pylint: disable=too-many-instance-attributes
    _aio_session: ClientSession
    _new_session_data: Optional[dict]
    _url: str
    _sid: Optional[str]
    _uid: Optional[str]
    _lang: str
    _l10n: Optional[dict]
    _devclass: Optional[str]
    _device_info_sensors: Sensors

    def __init__(
        self,
        session: ClientSession,
        url: str,
        password: Optional[str] = None,
        group: str = "user",
        uid: Optional[str] = None,
        lang: str = DEFAULT_LANG,
    ):
        """Init SMA connection.

        Args:
            session (ClientSession): aiohttp client session
            url (str): Url or IP address of device
            password (str, optional): Password to use during login. Defaults to None.
            group (str, optional): Username to use during login. Defaults to "user".
            uid (str, optional): uid used for data extraction. Defaults to None.
            lang (str, optional): Language code of file to retrieve. Defaults to "en-US".

        Raises:
            KeyError: User was not in USERS
        """
        # pylint: disable=too-many-arguments
        if group not in USERS:
            raise KeyError(f"Invalid user type: {group}")
        if password is not None and len(password) > 12:
            _LOGGER.warning("Password should not exceed 12 characters")
        if password is None:
            self._new_session_data = None
        else:
            self._new_session_data = {"right": USERS[group], "pass": password}
        self._url = url.rstrip("/")
        if not url.startswith("http"):
            self._url = "http://" + self._url
        self._aio_session = session
        self._sid = None
        self._uid = uid
        self._lang = lang
        self._l10n = None
        self._devclass = None
        self._debug = Debug_information_webconnect()
        self._device_info_sensors = Sensors(
            definitions_webconnect.sensor_map[DEVICE_INFO]
        )

    async def _request_json(
        self, method: str, url: str, **kwargs: Dict[str, Any]
    ) -> dict:
        """Request json data for requests.

        Args:
            method (str): HTTP method to use
            url (str): URL to do request to

        Raises:
            SmaConnectionException: Connection to device failed

        Returns:
            dict: json returned by device
        """
        if self._sid:
            kwargs.setdefault("params", {})
            kwargs["params"]["sid"] = self._sid

        _LOGGER.debug("Sending %s request to %s: %s", method, url, kwargs)

        max_retries = 2
        for retry in range(max_retries):
            try:
                async with self._aio_session.request(
                    method,
                    self._url + url,
                    timeout=ClientTimeout(total=DEFAULT_TIMEOUT),
                    **kwargs,
                ) as res:
                    res_json = await res.json()
                    _LOGGER.debug("Received reply %s", res_json)
                    return res_json or {}
            except (client_exceptions.ContentTypeError, json.decoder.JSONDecodeError):
                _LOGGER.warning("Request to %s did not return a valid json.", url)
                break
            except client_exceptions.ServerDisconnectedError as exc:
                if (retry + 1) < max_retries:
                    # For some reason the SMA device sometimes raises a server disconnected error
                    # If this happens we will retry up to `max_retries` times
                    # This  events errors in Home Assistant
                    _LOGGER.debug("ServerDisconnectedError, will retry connection.")
                    continue

                raise SmaConnectionException(
                    f"Server at {self._url} disconnected {max_retries+1} times."
                ) from exc
            except (
                client_exceptions.ClientError,
                asyncio.exceptions.TimeoutError,
            ) as exc:
                raise SmaConnectionException(
                    f"Could not connect to SMA at {self._url}: {exc}"
                ) from exc

        return {}

    async def _get_json(self, url: str) -> dict:
        """Get json data for requests.

        Args:
            url (str): URL to do GET request to

        Returns:
            dict: json returned by device
        """
        return await self._request_json(hdrs.METH_GET, url)

    async def _post_json(self, url: str, payload: Optional[dict] = None) -> dict:
        """Post json data for requests.

        Args:
            url (str): URL to do POST request to
            payload (dict, optional): payload to send to device. Defaults to empty dict.

        Returns:
            dict: json returned by device
        """
        if payload is None:
            payload = {}

        params: Dict[str, Any] = {
            "data": json.dumps(payload),
            "headers": {"content-type": "application/json"},
        }

        return await self._request_json(hdrs.METH_POST, url, **params)

    async def _read_l10n(self) -> dict:
        """Read device language file. Returns cached value on subsequent calls.

        Returns:
            dict: json returned by device
        """
        if self._l10n is None:
            self._l10n = await self._get_json(f"/data/l10n/{self._lang}.json")
            if len(self._l10n) == 0:
                _LOGGER.warning(
                    "Language '%s' not supported, fallback to '%s'",
                    self._lang,
                    DEFAULT_LANG,
                )
                self._l10n = await self._get_json(f"/data/l10n/{DEFAULT_LANG}.json")
        return self._l10n

    async def _read_body(self, url: str, payload: dict) -> dict:
        """Parse the json returned by the device and extract result.

        Args:
            url (str): URL to reqquest data from
            payload (dict): payload to send to device
        Raises:
            SmaReadException: The json returned by the device was in an unexpected format

        Returns:
            dict: json result
        """
        if self._sid is None and self._new_session_data is not None:
            await self.new_session()
        body = await self._post_json(url, payload)

        # On the first error we close the session which will re-login
        err = body.get("err")

        if err is not None:
            _LOGGER.warning(
                "%s: error detected, closing session to force another login attempt, got: %s",
                self._url,
                body,
            )
            await self.close_session()
            raise SmaReadException("Error detected while reading")

        if "result" not in body:
            _LOGGER.warning("No 'result' in reply from SMA, got: %s", body)
            raise SmaReadException("No 'result' in reply from SMA")

        if self._uid is None:
            # Get the unique ID
            self._uid = next(iter(body["result"].keys()), None)

        result_body = body["result"].pop(self._uid, None)
        if body != {"result": {}}:
            _LOGGER.warning(
                "Unexpected body %s, extracted %s",
                json.dumps(body),
                json.dumps(result_body),
            )

        return result_body

    # @override
    async def new_session(self) -> bool:
        """Establish a new session.

        Raises:
            SmaAuthenticationException: Authentication failed

        Returns:
            bool: authentication successful
        """
        body = await self._post_json(URL_LOGIN, self._new_session_data)
        self._sid = jmespath.search("result.sid", body)
        if self._sid:
            _LOGGER.debug("New SID: %s", self._sid)
            return True

        err = body.pop("err", None)
        msg = "Could not start session: %s"

        if err:
            if err == 503:
                _LOGGER.error(msg, "Max amount of sessions reached")
            elif err == 404:
                if not self._url.startswith("https"):
                    _LOGGER.error(msg, "Login URL not found, try using HTTPS")
                else:
                    _LOGGER.error(msg, "Login URL not found")
            else:
                _LOGGER.error(msg, err)
        else:
            _LOGGER.error(msg, "Session ID expected [result.sid]")

        raise SmaAuthenticationException()

    # @override
    async def close_session(self) -> None:
        """Close the session login."""
        if self._sid is None:
            return
        try:
            await self._post_json(URL_LOGOUT)
        finally:
            self._sid = None

    # @override
    async def read(self, sensors: Sensors, deviceID: str | None = None) -> bool:
        """Read a set of keys.

        Args:
            sensors (Sensors): Sensors object containing Sensor objects to read

        Returns:
            bool: reading was successful
        """
        if self._new_session_data is None:
            payload: Dict[str, Any] = {"destDev": [], "keys": []}
            result_body = await self._read_body(URL_DASH_VALUES, payload)
            self._debug.full_json = result_body
        else:
            payload = {
                "destDev": [],
                "keys": list({s.key for s in sensors if s.enabled}),
            }
            result_body = await self._read_body(URL_VALUES, payload)
            self._debug.last_json = result_body

        notfound = []
        l10n = await self._read_l10n()
        for sen in sensors:
            if sen.enabled:
                if sen.key in result_body:
                    sen.extract_value(result_body, l10n)
                    continue

                notfound.append(f"{sen.name} [{sen.key}]")

        if notfound:
            _LOGGER.info(
                "No values for sensors: %s. Response from inverter: %s",
                ",".join(notfound),
                result_body,
            )

        return True

    async def read_dash_logger(self) -> dict:
        """Read the dash loggers.

        Returns:
            dict: Dictionary containing loggers returned by device.
        """
        return await self._read_body(URL_DASH_LOGGER, {"destDev": [], "key": []})

    async def read_logger(self, log_id: int, start: int, end: int) -> list:
        """Read a logging key and return the results.

        Args:
            log_id (int): The ID of the log to read.
                totWhOut5min: 28672
                totWhOutDaily: 28704
                GridMsTotWhOutDaily: 28752
                GridMsTotWhInDaily: 28768
                ObjLogBatCha: 28816
                totWhIn5min: 28736
                totWhInDaily: 28768
                ObjLogBatChrg: 29344
                ObjLogBatDsch: 29360
            start (int): Start timestamp in seconds.
            end (int): End timestamp in seconds.

        Returns:
            list: The log entries returned by the device
        """
        payload = {
            "destDev": [],
            "key": log_id,
            "tStart": start,
            "tEnd": end,
        }
        result_body = await self._read_body(URL_LOGGER, payload)
        if not isinstance(result_body, list):
            raise SmaReadException("List of log entries expected.")

        return result_body

    # @override
    async def device_info(self) -> dict:
        """Read device info and return the results.

        Returns:
            dict: dict containing serial, name, type, manufacturer and sw_version
        """
        di = await self.device_list()
        return list(di.values())[0].asDict()

    # @override
    async def device_list(self) -> dict[str, DeviceInformation]:
        await self.read(self._device_info_sensors)

        sen = self._device_info_sensors
        di = DeviceInformation(
            sen["serial_number"].value or FALLBACK_DEVICE_INFO["serial"],
            sen["serial_number"].value or FALLBACK_DEVICE_INFO["serial"],
            sen["device_name"].value or FALLBACK_DEVICE_INFO["name"],
            sen["device_type"].value or FALLBACK_DEVICE_INFO["type"],
            sen["device_manufacturer"].value or FALLBACK_DEVICE_INFO["manufacturer"],
            version_int_to_string(self._device_info_sensors["device_sw_version"].value),
        )
        self._debug.device_info = di
        return {di.serial: di}

    async def _read_all_sensors(self) -> dict:
        all_values = await self._read_body(URL_ALL_VALUES, {"destDev": []})
        all_params = await self._read_body(URL_ALL_PARAMS, {"destDev": []})
        self._debug.all_values = all_values
        self._debug.all_params = all_params
        return all_values | all_params

    # @override
    async def get_sensors(self, deviceID: str | None = None) -> Sensors:
        """Get the sensors that are present on the device.

        Returns:
            Sensors: Sensors object containing Sensor objects
        """
        all_sensors = await self._read_all_sensors()
        sensor_keys = all_sensors.keys()
        device_sensors = Sensors()

        _LOGGER.debug("Matching generic sensors")

        for sensor in definitions_webconnect.sensor_map[GENERIC_SENSORS]:
            if sensor.key in sensor_keys:
                if isinstance(all_sensors[sensor.key], list):
                    # SB1.5 multi value
                    val_len = len(all_sensors[sensor.key])
                elif "val" in all_sensors[sensor.key]:
                    # SB1.5 single value
                    val_len = 1
                else:
                    # All other types, single or multi value
                    sensors_values = list(all_sensors[sensor.key].values())[0]
                    val_len = len(sensors_values)
                _LOGGER.debug("Found %s with %d value(s).", sensor.key, val_len)

                if sensor.key_idx < val_len:
                    _LOGGER.debug(
                        "Adding sensor %s (%s_%s)",
                        sensor.name,
                        sensor.key,
                        sensor.key_idx,
                    )
                    device_sensors.add(sensor)

        _LOGGER.debug("Checking if Energy Meter is present...")
        # Detect and add Energy Meter sensors
        em_sensor = copy.copy(definitions_webconnect.energy_meter)
        em_sensor.extract_value(all_sensors)

        if em_sensor.value:
            _LOGGER.debug(
                "Energy Meter with serial %s detected. Adding extra sensors.",
                em_sensor.value,
            )
            device_sensors.add(
                [
                    sensor
                    for sensor in definitions_webconnect.sensor_map[
                        ENERGY_METER_VIA_INVERTER
                    ]
                    if sensor not in device_sensors
                ]
            )

        _LOGGER.debug("Finding connected optimizers...")
        # Detect and add Optimizer Sensors
        optimizers = all_sensors.get(definitions_webconnect.optimizer_serial.key)
        if optimizers:
            serials = optimizers.popitem()[1]

            for idx, serial in enumerate(serials or []):
                if serial["val"]:
                    _LOGGER.debug(
                        "Optimizer %s with serial %s detected. Adding extra sensors.",
                        idx,
                        serial,
                    )
                    for sensor_definition in definitions_webconnect.sensor_map[
                        OPTIMIZERS_VIA_INVERTER
                    ]:
                        new_sensor = copy.copy(sensor_definition)
                        new_sensor.key_idx = idx
                        new_sensor.name = f"{sensor_definition.name}_{idx}"
                        self._sensors = device_sensors
        return device_sensors

    def known_sensors(self) -> list[Sensor]:
        """Return the sensors currently known to the live session, without I/O."""
        return list(self._sensors) if hasattr(self, "_sensors") and self._sensors else []

    # @override
    async def get_debug(self) -> Dict:
        debug = asdict(self._debug)
        debug["device_info_sensors"] = self._device_info_sensors
        debug["url"] = self._url
        return debug

    # @override
    async def detect(self, ip: str) -> list[DiscoveryInformation]:
        results = []
        for urls in ["https://" + ip, "http://" + ip]:
            self._url = urls
            di = DiscoveryInformation()
            di.remark = urls
            try:
                di.tested_endpoints = self._url
                await self.new_session()
            except SmaAuthenticationException as e:
                if self._sid:
                    di.status = "found"
                    di.exception = e
                else:
                    di.status = "failed"
                    di.exception = e
            except Exception as e:  # pylint: disable=broad-exception-caught
                di.status = "failed"
                di.exception = e
            results.append(di)
        return results

    # @override
    async def set_parameter(
        self, sensor: Sensor, value: int, deviceID: str | None = None
    ) -> None:
        """Set Parameters."""
        if sensor.webconnect_deviceId is None:
            _LOGGER.info(
                f"Cannot set Parameter {sensor} {value} {deviceID}. Device ID could not be determined."
            )
            return

        key = sensor.key
        requestData = {
            "destDev": [],
            "values": [{str(key): {sensor.webconnect_deviceId: [value]}}],
        }
        ret = await self._post_json(URL_SETPARAMETER, requestData)
        _LOGGER.info(
            f"Set_Paramter {sensor} {value} {deviceID} {sensor.webconnect_deviceId} Return {ret}"
        )
