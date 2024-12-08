"""
Implementation for SMA Speedwire

Improved with Information from https://github.com/mhop/fhem-mirror/blob/master/fhem/FHEM/76_SMAInverter.pm
Receiver classes completely reimplemented by little.yoda

"""

import asyncio
import binascii
import collections
import copy
import logging
import struct
import time
from asyncio import DatagramProtocol, Future
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from .const import SMATagList
from .definitions_speedwire import (
    SpeedwireFrame,
    commands,
    responseDef,
    speedwireHeader,
    speedwireHeader6065,
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

NO_HANDLER_FOR_MIN_TIMEDELTA = timedelta(hours=24) # How often to report a "known unknown" response

class SMAClientProtocol(DatagramProtocol):
    """Basic Class for communication"""

    _commandFuture: Future[Any] | None = None

    debug: Dict[str, Any] = {
        "msg": collections.deque(maxlen=len(commands) * 10),
        "data": {},
        "unfinished": set(),
        "ids": set(),
        "sendcounter": 0,
        "resendcounter": 0,
        "failedCounter": 0,
        "warned": {}, # dictionary of "No handler for" adresses with timestamp of last logged message, 
        # so it can be repeated daily (instead of per poll)
    }

    def __init__(
        self, password: str, on_connection_lost: Future, options: Dict[str, Any]
    ):
        self._lastSend: float = 0
        self._firstSend: float | None = None
        self.speedwire = SpeedwireFrame()
        self._transport = None
        self.password = password
        self.on_connection_lost = on_connection_lost
        self.cmds: list[str] = []
        self.cmdidx = 0
        self.future: Future | None = None
        self.data_values: dict[str, Any] = {}
        self.sensors: dict[str, Sensor] = {}
        self._group = ""
        self._resendcounter = 0
        self._defaultRetries = int(options.get("defaultRetries", 2))
        self._loginRetries = int(options.get("loginRetries", 3))
        self._loggedIn = False
        self._failedCounter = 0
        self._sendCounter = 0
        self._commandTimeout = float(options.get("commandTimeout", 0.5))
        self._commandDelay = float(options.get("commandDelay", 0.0))
        self._overallTimeout = max(
            5 + len(commands) * (self._commandDelay) * 2,
            (self._commandTimeout + self._commandDelay)
            * (max(self._loginRetries, self._loginRetries) + 1),
        )
        self._overallTimeout = float(
            options.get("overallTimeout", self._overallTimeout)
        )
        self.allCmds: list[str] = []
        self.allCmds.extend(commands.keys())
        self.allCmds.remove("login")
        self.allCmds.remove("logoff")

    def connection_made(self, transport: Any) -> None:
        self._transport = transport

    async def controller(self) -> None:
        try:
            if self._resendcounter == 0:
                self.debug["sendcounter"] += 1
                self._sendCounter += 1
            if self._commandFuture is None:
                raise RuntimeError("_commandFuture not send")
            await asyncio.wait_for(self._commandFuture, timeout=self._commandTimeout)
            self.cmdidx += 1
            self._resendcounter = 0
        except (asyncio.TimeoutError, RuntimeError):
            _LOGGER.debug(f"Timeout in command. Resendcounter: {self._resendcounter}")
            self._resendcounter += 1
            self.debug["resendcounter"] += 1
            retries = self._defaultRetries
            if self.cmds[self.cmdidx] == "login":
                retries = self._loginRetries
            _LOGGER.debug(
                f"Timeout in command. Resendcounter: {self._resendcounter} {retries}"
            )
            if self._resendcounter > retries:
                # Giving up. Next Command
                if self.cmds[self.cmdidx] == "login":
                    self.future.set_exception(
                        SmaConnectionException("Login failed! No Response from Device!")
                    )
                _LOGGER.debug("Timeout in command")
                self.cmdidx += 1
                self._resendcounter = 0
                self._failedCounter += 1
                self.debug["failedCounter"] += 1
        await self._send_next_command()

    def _confirm_repsonse(self, code: int = -1):
        """Mark the commandFuture as done"""
        if self._commandFuture is None or self._commandFuture.done():
            _LOGGER.debug(f"unexpected message {code:08X}")
            return
        self._commandFuture.set_result(True)

    async def start_query(self, cmds: List, future: Future, group: str) -> None:
        self.cmds = []
        if not self._loggedIn:
            self.cmds.append("login")
        self.cmds.extend(cmds)
        self.future = future
        self.cmdidx = 0
        self._failedCounter = 0
        self._sendCounter = 0
        self._group = group
        self.data_values = {}
        self.sensors = {}
        _LOGGER.debug("Sending login")
        self.debug["msg"].append(["SEND", "login"])
        self._firstSend = time.time()
        await self._send_next_command()

    def connection_lost(self, exc: Exception | None) -> None:
        """connection lost handler"""
        _LOGGER.debug("Connection lost: %s %s", type(exc), exc)
        self._loggedIn = False
        self.on_connection_lost.set_result(True)

    def _send_command(self, cmd: bytes) -> None:
        """Send the Command"""
        _LOGGER.debug(
            f"Sending command [{len(cmd)}] -- {binascii.hexlify(cmd).upper()}"  # type: ignore[str-bytes-safe]
        )
        self._commandFuture = asyncio.get_running_loop().create_future()
        asyncio.get_running_loop().create_task(self.controller())
        if self._transport is None:
            raise RuntimeError("Transport is None")
        self._transport.sendto(cmd)

    async def logoff(self) -> None:
        try:
            self._send_command(self.speedwire.getLogoutFrame(0))
            await asyncio.sleep(0.2)  # Wait for delayed responses
        except RuntimeError:
            pass

    async def _send_next_command(self) -> None:
        """Send the next command in the list"""
        if not self.future:
            return
        if self.cmdidx >= len(self.cmds):
            # All commands send. Clean up.
            f = self.future
            self.future = None
            await asyncio.sleep(0.2)  # Wait for delayed responses
            self.debug["data"] = self.data_values
            self.cmds = []
            self.cmdidx = 0
            if not f.done():
                f.set_result(True)
            if self._firstSend:
                self.debug["msg"].append(
                    ["TOTAL", 0, "", round(time.time() - self._firstSend, 2)]
                )
                self._firstSend = None

        else:
            if self._resendcounter == 0:
                await asyncio.sleep(self._commandDelay)
            # Send the next command
            self.debug["msg"].append(["SEND", self.cmds[self.cmdidx]])
            _LOGGER.debug("Sending " + self.cmds[self.cmdidx])
            self._lastSend = time.time()
            if (self.cmds[self.cmdidx]) == "login":
                groupidx = ["user", "installer"].index(self._group) == 1
                self._send_command(
                    self.speedwire.getLoginFrame(self.password, 0, groupidx)
                )
            else:
                self._send_command(
                    self.speedwire.getQueryFrame(0, self.cmds[self.cmdidx])
                )

    def _getFormat(self, handler: dict) -> tuple:
        """Return the necessary information for extracting the information"""
        converter = None
        format = handler.get("format", "")
        if format == "int":
            format = "<l"
        elif format == "" or format == "uint":
            format = "<L"
        elif format == "version":
            format = "<L"
            converter = version_int_to_string
        else:
            raise ValueError(f"Unknown Format {format}")
        size = struct.calcsize(format)
        return (format, size, converter)

    def handle_login(self, msg: speedwireHeader6065) -> None:
        """Is called if a login response is received"""
        _LOGGER.debug("Login rppsonse received!")
        self.sensors = {}
        self.data_values = {"error": msg.error}
        self.data_values["serial"] = str(msg.src_serial)
        if msg.error == 256:
            _LOGGER.error("Login failed!")
            if self.future:
                self.future.set_exception(
                    SmaAuthenticationException(
                        "Login failed! Credentials wrong (user/install or password)"
                    )
                )
        else:
            self._loggedIn = True

    def handle_newvalue(self, sensor: Sensor, value: Any, overwrite: bool) -> None:
        """Set the new value to the sensor"""
        if value is None:
            return
        sen = copy.copy(sensor)
        if sen.factor and sen.factor != 1:
            value /= sen.factor
        sen.value = value
        if sen.key in self.sensors:
            oldValue = self.sensors[sen.key].value
            if oldValue != value:
                # _LOGGER.warning(
                #     f"Sensors {sen.key} {sen.name} Old Value: {oldValue} New values: {sen.value} Overwrite: {overwrite}"
                # )
                if not overwrite:
                    value = oldValue
        self.sensors[sen.key] = sen
        self.data_values[sen.key] = value

    def extractvalues(self, handler: Dict, subdata: bytes) -> list[Any]:
        (formatdef, size, converter) = self._getFormat(handler)
        values = []
        for idx in range(8, len(subdata), size):
            v = struct.unpack(formatdef, subdata[idx : idx + size])[0]
            if v in [0xFFFFFFFF, 0x80000000, 0xFFFFFFEC, -0x80000000, 0xFFFFFE]:
                v = None
            else:
                if converter:
                    v = converter(v)
                if "mask" in handler:
                    v = v & handler["mask"]
            values.append(v)
        return values

    def fixID(self, orig: str) -> str:
        if orig in responseDef:
            return orig
        for code in responseDef.keys():
            if code[0:7] == orig[:7]:
                return code
        return orig

    def handle_register(self, subdata: bytes, register_idx: int) -> None:
        """Handle the payload with all the registers"""
        code = int.from_bytes(subdata[0:4], "little")
        # c = f"{(code & 0xFFFFFFFF):08X}"
        c = f"{code:08X}"
        msec = int.from_bytes(subdata[4:8], "little")  # noqa: F841

        # Fix for strange response codes
        self.debug["ids"].add(c[6:])
        self._id = c[6:]
        c = self.fixID(c)

        # Handle unknown Responses
        if c not in responseDef:
            values = []
            valuesPos = []
            for idx in range(8, len(subdata), 4):
                v = struct.unpack("<l", subdata[idx : idx + 4])[0]
                values.append(v)
                valuesPos.append(f"{idx + 54}")
            # check if the value 'c' was already logged within the last 24 hrs (TIMEDELTA def above)


            if ((ts := self.debug.get("warned",{}).get(c)) 
                and ts>(datetime.now()-NO_HANDLER_FOR_MIN_TIMEDELTA)):
                # do not warn again
                # it also already known to "unfinished" set
                return

            _LOGGER.warning(f"No Handler for {c}: {values} @ {valuesPos}")
            self.debug["unfinished"].add(f"{c}")
            self.debug["warned"][c]=datetime.now() # add to known unknowns that have been warned
            return

        # Handle known repsones
        for handler in responseDef[c]:
            values = self.extractvalues(handler, subdata)
            if "sensor" not in handler:
                continue
            v = None
            if handler["idx"] == 0xFF:
                """For some responses, a list is returned and the correct value
                within this list is marked by the top 8 bits."""
                for origValue in values:
                    if origValue is not None and (origValue & 0xFF000000) > 0:
                        v = origValue & 0x00FFFFFF
                        break
            else:
                v = values[handler["idx"]]

            sensor = handler["sensor"]

            # Special handling for a response that returns two values under the same code
            if isinstance(sensor, List):
                if register_idx >= len(sensor):
                    _LOGGER.warning(
                        f"No Handler for {c} at register idx {register_idx}: {values}"
                    )
                    continue
                _LOGGER.debug(
                    f"Special Handler for {c} at register idx {register_idx}: {values}"
                )
                sensor = sensor[register_idx]
            _LOGGER.debug(
                f"ID: {self._id} Values {sensor.name}/{sensor.key}: {v} {values}"
            )
            self.handle_newvalue(sensor, v, handler.get("overwrite", True))

    # Unfortunately, there is no known method of determining the size of the registers
    # from the message. Therefore, the register size is determined from the number of
    # registers and the size of the payload.
    def calc_register(self, data: bytes, msg: speedwireHeader6065) -> tuple:
        cnt_registers = msg.lastRegister - msg.firstRegister + 1
        size_datapayload = len(data) - 54 - 4
        size_registers = (
            size_datapayload // cnt_registers
            if size_datapayload % cnt_registers == 0
            else -1
        )
        return (cnt_registers, size_registers)

    # Main routine for processing received messages.
    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        _LOGGER.debug(f"RECV: {addr} Len:{len(data)} {binascii.hexlify(data).upper()}")  # type: ignore[str-bytes-safe]
        delta = 0.0
        if self._lastSend > 0:
            delta = time.time() - self._lastSend
            self._lastSend = 0
        self.debug["msg"].append(
            [
                "RECV",
                len(data),
                binascii.hexlify(data).upper().decode("utf-8"),
                round(delta, 2),
            ]
        )

        # Check if message is a 6065 protocol
        msg = speedwireHeader.from_packed(data[0:18])
        if not msg.check6065():
            _LOGGER.debug("Ignoring non 6065 Response. %d", msg.protokoll)
            return

        # If the requested information is not available, send the next command,
        if len(data) < 58:
            _LOGGER.debug(f"NACK [{len(data)}] -- {data!r}")
            self._confirm_repsonse()
            return

        # Handle Login Responses
        msg6065 = speedwireHeader6065.from_packed(data[18 : 18 + 36])
        if msg6065.isLoginResponse():
            self.handle_login(msg6065)
            self._confirm_repsonse()
            return

        # Filter out non matching responses
        (cnt_registers, size_registers) = self.calc_register(data, msg6065)
        code = int.from_bytes(data[54:58], "little")
        codem = code & 0x00FFFF00
        if len(data) == 58 and codem == 0:
            _LOGGER.debug(f"NACK [{len(data)}] -- {data!r}")
            self._confirm_repsonse()
            return
        if size_registers <= 0 or size_registers not in [16, 28, 40]:
            _LOGGER.warning(
                f"Skipping message. --- Len {data!r} Ril {codem} {cnt_registers} x {size_registers} bytes"
            )
            self._confirm_repsonse(code)
            return

        # Extract the values for each register
        for idx in range(0, cnt_registers):
            start = idx * size_registers + 54
            self.handle_register(data[start : start + size_registers], idx)

        self._confirm_repsonse(code)


class SMAspeedwireINV(Device):
    """Adapter between Device-Class and SMAClientProtocol"""

    _options: Dict[str, Any] = {}
    _transport = None
    _protocol = None
    _deviceinfo: DeviceInformation
    _debug: Dict[str, Any] = {"overalltimeout": 0}

    def __init__(self, host: str, group: str, password: Optional[str]):
        self._host = host
        self._group = group
        self._password = password
        if group not in ["user", "installer"]:
            raise KeyError(f"Invalid user type: {group} (user or installer)")

    async def _createEndpoint(self) -> None:
        if self._protocol is not None:
            _LOGGER.warning("Protocol already created")
            return
        loop = asyncio.get_running_loop()
        on_connection_lost = loop.create_future()
        if not self._password:
            raise ValueError("Password not set!")
        if len(self._password) > 12:
            raise ValueError("Password to long! Max 12 Characters.")
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: SMAClientProtocol(
                self._password,  # type: ignore[arg-type]
                on_connection_lost,
                self._options,
            ),
            remote_addr=(self._host, 9522),
        )

    # @override
    async def new_session(self) -> bool:
        # Create Endpoint
        await self._createEndpoint()
        if self._protocol is None:
            raise SmaConnectionException("protocol not initialized")

        self._protocol._failedCounter = 0
        self._protocol._sendCounter = 0
        # Test with device_info if the ip and user/pwd are correct
        await self.device_info()
        if self._protocol._failedCounter >= self._protocol._sendCounter:
            raise SmaConnectionException(
                f"No connection to device: {self._host}:9522  ({self._protocol._failedCounter}/{self._protocol._sendCounter})"
            )
        return True

    # @override
    async def device_info(self) -> dict:
        ll = await self.device_list()
        return list(ll.values())[0].asDict()

    # @override
    async def device_list(self) -> dict[str, DeviceInformation]:
        if self._protocol is None:
            raise SmaConnectionException("protocol not initialized")

        fut = asyncio.get_running_loop().create_future()
        await self._protocol.start_query(["TypeLabel", "Firmware"], fut, self._group)
        try:
            await asyncio.wait_for(fut, timeout=self._protocol._overallTimeout)
        except TimeoutError:
            self._debug["overalltimeout"] += 1
            _LOGGER.warning("Timeout in device_info")
            if (
                "error" in self._protocol.data_values
                and self._protocol.data_values["error"] == 0
            ):
                raise SmaReadException(
                    "Reply for request not received"
                )  # Recheck Logic
            raise SmaConnectionException("No connection to device")
        data = self._protocol.data_values

        invcnr = data.get("inverter_class", 0)
        invc = SMATagList.get(invcnr, f"Unknown device ({invcnr})")

        invtnr = data.get("inverter_type", 0)
        invt = SMATagList.get(invtnr, f"Unknown type ({invtnr})")

        self._deviceinfo = DeviceInformation(
            data.get("serial", ""),
            data.get("serial", ""),
            str(invt),
            str(invc),
            "SMA",
            data.get("Firmware", ""),
        )
        return {data.get("serial", ""): self._deviceinfo}

    # @override
    async def get_sensors(self, deviceID: str | None = None) -> Sensors:
        if self._protocol is None:
            raise SmaConnectionException("protocol not initialized")

        fut = asyncio.get_running_loop().create_future()
        c = self._protocol.allCmds
        device_sensors = Sensors()
        try:
            await self._protocol.start_query(c, fut, self._group)
            await asyncio.wait_for(fut, timeout=self._protocol._overallTimeout)
            for s in self._protocol.sensors.values():
                device_sensors.add(s)
        except asyncio.TimeoutError as e:
            self._debug["overalltimeout"] += 1
            raise e
        return device_sensors

    # @override
    async def read(self, sensors: Sensors, deviceID: str | None = None) -> bool:
        if self._protocol is None:
            raise SmaConnectionException("protocol not initialized")

        fut = asyncio.get_running_loop().create_future()
        c = self._protocol.allCmds
        await self._protocol.start_query(c, fut, self._group)
        try:
            await asyncio.wait_for(fut, timeout=self._protocol._overallTimeout)
            self._update_sensors(sensors, self._protocol.sensors, deviceID)
            return True
        except asyncio.TimeoutError as e:
            self._debug["overalltimeout"] += 1
            raise e

    def _update_sensors(
        self, sensors: Sensors, sensorReadings: dict[str, Sensor], deviceID: str | None
    ) -> None:
        """Update a sensor with the sensor reading"""
        _LOGGER.debug("Received %d sensor readings", len(sensorReadings))
        for sen in sensors:
            if sen.enabled and sen.key in sensorReadings:
                value = sensorReadings[sen.key].value
                if sen.mapper:
                    sen.mapped_value = sen.mapper.get(value, str(value))
                sen.value = value

    async def close_session(self) -> None:
        if self._transport is not None:
            await self._protocol.logoff()
            self._transport.close()
            self._trasport = None

    async def get_debug(self) -> Dict:
        if self._protocol is None:
            raise SmaConnectionException("protocol not initialized")

        ret = self._protocol.debug.copy()
        ret["unfinished"] = list(ret["unfinished"])
        ret["msg"] = list(ret["msg"])
        ret["ids"] = list(ret["ids"])
        ret["device_info"] = self._deviceinfo
        ret["timeouts"] = self._debug["overalltimeout"]
        return ret

    # wait for a response or a timeout
    async def detect(self, ip: str) -> list[DiscoveryInformation]:
        di = DiscoveryInformation()
        di.tested_endpoints = str(ip) + ":9522"
        try:
            await self.new_session()
            if self._protocol is None:
                raise SmaConnectionException("protocol not initialized")
            fut = asyncio.get_running_loop().create_future()
            await self._protocol.start_query(["TypeLabel"], fut, self._group)
            try:
                await asyncio.wait_for(fut, timeout=5)
            except TimeoutError:
                _LOGGER.warning("Timeout in detect")
            if (
                "error" in self._protocol.data_values
                and self._protocol.data_values["error"] == 0
            ):
                raise SmaReadException("Reply for request not received")
            raise SmaConnectionException("No connection to device")
        except SmaAuthenticationException as e:
            di.status = "maybe"
            di.exception = e
            di.remark = "only unencrypted Speedwire is supported"
        except Exception as e:
            di.status = "failed"
            di.exception = e
        return [di]

    def set_options(self, options: Dict[str, Any]) -> None:
        self._options = options
