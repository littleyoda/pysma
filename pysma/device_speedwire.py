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
import sys
import time
from asyncio import DatagramProtocol, Future
from typing import Annotated, Any, Dict, List, Optional

from .const import SMATagList
from .definitions_speedwire import (
    SpeedwireFrame,
    commands,
    responseDef,
    speedwireHeader,
    speedwireHeader6065,
)
from .device import Device
from .exceptions import (
    SmaAuthenticationException,
    SmaConnectionException,
    SmaReadException,
)
from .helpers import version_int_to_string
from .sensor import Sensor, Sensors

_LOGGER = logging.getLogger(__name__)


class SMAClientProtocol(DatagramProtocol):
    """Basic Class for communication"""

    _commandFuture: Future[Any] = None

    debug: Dict[str, Any] = {
        "msg": collections.deque(maxlen=len(commands) * 10),
        "data": {},
        "unfinished": set(),
        "ids": set(),
        "sendcounter": 0,
        "resendcounter": 0,
        "failedCounter": 0,
    }

    def __init__(self, password, on_connection_lost, options: Dict[str, any]):
        self._lastSend = None
        self._firstSend = None
        self.speedwire = SpeedwireFrame()
        self.transport = None
        self.password = password
        self.on_connection_lost = on_connection_lost
        self.cmds = []
        self.cmdidx = 0
        self.future = None
        self.data_values = {}
        self.sensors = {}
        self._group = None
        self._resendcounter = 0
        self._failedCounter = 0
        self._sendCounter = 0
        self._commandTimeout = float(options.get("commandTimeout", 0.5))
        self._commandDelay = float(options.get("commandDelay", 0.0))
        self._overallTimeout = float(
            options.get("overallTimeout", 5 + len(commands) * (self._commandDelay))
        )
        #        print("Timeouts", len(commands), self._commandTimeout, self._commandDelay, self._overallTimeout)
        self.allCmds = []
        self.allCmds.extend(commands.keys())
        self.allCmds.remove("login")
        self.allCmds.remove("logoff")

    def connection_made(self, transport):
        self.transport = transport

    async def controller(self):
        try:
            if self._resendcounter == 0:
                self.debug["sendcounter"] += 1
                self._sendCounter += 1

            await asyncio.wait_for(self._commandFuture, timeout=self._commandTimeout)
            self.cmdidx += 1
            self._resendcounter = 0
        except asyncio.TimeoutError:
            _LOGGER.debug(f"Timeout in command. Resendcounter: {self._resendcounter}")
            self._resendcounter += 1
            self.debug["resendcounter"] += 1
            if self._resendcounter > 2:
                # Giving up. Next Command
                _LOGGER.debug(f"Timeout in command")
                self.cmdidx += 1
                self._resendcounter = 0
                self._failedCounter += 1
                self.debug["failedCounter"] += 1
        await self._send_next_command()

    def _confirm_repsonse(self, code=-1):
        if self._commandFuture.done():
            _LOGGER.debug(f"unexpected message {code:08X}")
            return
        self._commandFuture.set_result(True)

    async def start_query(self, cmds: List, future, group: str):
        self.cmds = ["login"]
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

    def connection_lost(self, exc):
        _LOGGER.debug(f"Connection lost: {exc}")
        self.on_connection_lost.set_result(True)

    def _send_command(self, cmd):
        """Send the Command"""
        _LOGGER.debug(
            f"Sending command [{len(cmd)}] -- {binascii.hexlify(cmd).upper()}"
        )
        self._commandFuture = asyncio.get_running_loop().create_future()
        asyncio.get_running_loop().create_task(self.controller())
        self.transport.sendto(cmd)

    async def _send_next_command(self):
        """Send the next command in the list"""
        if not self.future:
            return
        if self.cmdidx >= len(self.cmds):
            # All commands send. Clean up.
            f = self.future
            self.future = None
            await asyncio.sleep(0.2)  # Wait for delayed respones
            self.debug["data"] = self.data_values
            self.cmds = []
            self.cmdidx = 0
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
                groupidx = ["user", "installer"].index(self._group)
                self._send_command(
                    self.speedwire.getLoginFrame(self.password, 0, groupidx)
                )
            else:
                self._send_command(
                    self.speedwire.getQueryFrame(
                        self.password, 0, self.cmds[self.cmdidx]
                    )
                )

    def _getFormat(self, handler):
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

    def handle_login(self, msg):
        """Is called if a login repsonse is received"""
        _LOGGER.debug("Login repsonse received!")
        self.sensors = {}
        self.data_values = {"error": msg.error}
        if msg.error == 256:
            _LOGGER.error("Login failed!")
            self.future.set_exception(
                SmaAuthenticationException(
                    "Login failed! Credentials wrong (user/install or password)"
                )
            )

    def handle_newvalue(self, sensor: Sensor, value: Any, overwrite: bool):
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
                _LOGGER.warning(
                    f"Sensors {sen.key} {sen.name} Old Value: {oldValue} New values: {sen.value} Overwrite: {overwrite}"
                )
                if not overwrite:
                    value = oldValue
        self.sensors[sen.key] = sen
        self.data_values[sen.key] = value

    def extractvalues(self, handler: Dict, subdata):
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

    def fixID(self, orig):
        if orig in responseDef:
            return orig
        for code in responseDef.keys():
            if code[0:7] == orig[:7]:
                return code
        return orig

    def handle_register(self, subdata, register_idx: int):
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
            _LOGGER.warning(f"No Handler for {c}: {values} @ {valuesPos}")
            self.debug["unfinished"].add(f"{c}")
            return

        # Handle known repsones
        for handler in responseDef[c]:
            values = self.extractvalues(handler, subdata)
            if "sensor" not in handler:
                continue
            v = None
            if handler["idx"] == 0xFF:
                """For some responses, a list is returned and the correct value
                wihtin this list is marked by the top 8 bits."""
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
    def calc_register(self, data, msg: speedwireHeader6065):
        cnt_registers = msg.lastRegister - msg.firstRegister + 1
        size_datapayload = len(data) - 54 - 4
        size_registers = (
            size_datapayload // cnt_registers
            if size_datapayload % cnt_registers == 0
            else -1
        )
        return (cnt_registers, size_registers)

    # Main routine for processing received messages.
    def datagram_received(self, data, addr):
        _LOGGER.debug(f"RECV: {addr} Len:{len(data)} {binascii.hexlify(data).upper()}")
        delta = 0
        if self._lastSend:
            delta = time.time() - self._lastSend
            self._lastSend = None
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
            _LOGGER.debug(f"NACK [{len(data)}] -- {data}")
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
            _LOGGER.debug(f"NACK [{len(data)}] -- {data}")
            self._confirm_repsonse()
            return
        if size_registers <= 0 or size_registers not in [16, 28, 40]:
            _LOGGER.warning(
                f"Skipping message. --- Len {data} Ril {codem} {cnt_registers} x {size_registers} bytes"
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
    _deviceinfo: Dict[str, Any] = {}
    _debug: Dict[str, Any] = {"overalltimeout": 0}

    def __init__(self, host: str, group: str, password: Optional[str]):
        self._host = host
        self._group = group
        self._password = password
        if group not in ["user", "installer"]:
            raise KeyError(f"Invalid user type: {group} (user or installer)")

        self.check()

    def check(self) -> None:
        keysname = {}
        sensorname = {}
        for responses in responseDef.values():
            for response in responses:
                if "sensor" not in response or not isinstance(
                    response["sensor"], Sensor
                ):
                    continue
                sensor = response["sensor"]
                if sensor.key in keysname:
                    print("Doppelter SensorKey " + sensor.key)
                    raise RuntimeError("Doppelter SensorKey " + sensor.key)
                keysname[sensor.key] = 1
                if sensor.name in sensorname:
                    print("Doppelter SensorName " + sensor.name)
                    raise RuntimeError("Doppelter Sensorname " + sensor.name)
                sensorname[sensor.name] = 1

        keysname = {}
        sensorname = {}
        for x in commands.items():
            if "registers" not in x[1]:
                continue
            for r in x[1]["registers"]:
                if "name" in r:
                    name = r["name"]
                    if name in keysname:
                        print("Doppelter Keyname " + name)
                        raise RuntimeError("Doppelter Keyname " + name)
                    keysname[name] = 1
                if "sensor" in r:
                    sensor = r["sensor"]
                    if isinstance(sensor, Sensor) and sensor.key in sensorname:
                        print("Doppelter Sensorname " + sensor.key)
                        raise RuntimeError("Doppelter Sensorname " + sensor.key)
                    sensorname[name] = 1

    async def _createEndpoint(self):
        loop = asyncio.get_running_loop()
        on_connection_lost = loop.create_future()
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: SMAClientProtocol(
                self._password, on_connection_lost, self._options
            ),
            remote_addr=(self._host, 9522),
        )

    async def new_session(self) -> bool:
        # Create Endpoint
        await self._createEndpoint()

        # Test with device_info if the ip and user/pwd are correct
        await self.device_info()
        if self._protocol._failedCounter >= self._protocol._sendCounter:
            raise SmaConnectionException("No connection to device: %s:9522", self._host)

    async def device_info(self) -> dict:
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
        invc = SMATagList.get(invcnr, "Unknown device")

        invtnr = data.get("inverter_type", 0)
        invt = SMATagList.get(invtnr, "Unknown type")
        self._deviceinfo = {
            "serial": data.get("serial", ""),
            "name": str(invt) + " (" + str(invtnr) + ")",
            "type": str(invc) + " (" + str(invcnr) + ")",
            "manufacturer": "SMA",
            "sw_version": data.get("Firmware", ""),
        }
        return self._deviceinfo

    async def get_sensors(self) -> Sensors:
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

    async def read(self, sensors: Sensors) -> bool:
        fut = asyncio.get_running_loop().create_future()
        c = self._protocol.allCmds
        await self._protocol.start_query(c, fut, self._group)
        try:
            await asyncio.wait_for(fut, timeout=self._protocol._overallTimeout)
            self._update_sensors(sensors, self._protocol.sensors)
            return True
        except asyncio.TimeoutError as e:
            self._debug["overalltimeout"] += 1
            raise e

    def _update_sensors(self, sensors, sensorReadings):
        """Update a sensor with the sensor reading"""
        _LOGGER.debug("Received %d sensor readings", len(sensorReadings))
        for sen in sensors:
            if sen.enabled and sen.key in sensorReadings:
                value = sensorReadings[sen.key].value
                if sen.mapper:
                    sen.mapped_value = sen.mapper.get(value, str(value))
                sen.value = value

    async def close_session(self) -> None:
        self._transport.close()

    async def get_debug(self) -> Dict:
        ret = self._protocol.debug.copy()
        ret["unfinished"] = list(ret["unfinished"])
        ret["msg"] = list(ret["msg"])
        ret["ids"] = list(ret["ids"])
        ret["device_info"] = self._deviceinfo
        ret["timeouts"] = self._debug["overalltimeout"]
        return ret

    # wait for a response or a timeout
    async def detect(self, ip) -> bool:
        ret = await super().detect(ip)
        try:
            ret[0]["testedEndpoints"] = str(ip) + ":9522"
            await self.new_session()
            fut = asyncio.get_running_loop().create_future()
            await self._protocol.start_query(["TypeLabel"], fut, self._group)
            try:
                await asyncio.wait_for(fut, timeout=5)
            except TimeoutError:
                _LOGGER.warning("Timeout in detect")
            if (
                "error" in self._protocol.data_values
                and self._protocol.dataValuess["error"] == 0
            ):
                raise SmaReadException(
                    "Reply for request not received"
                )  ## TODO recheck logic
            raise SmaConnectionException("No connection to device")
        except SmaAuthenticationException as e:
            ret[0]["status"] = "maybe"
            ret[0]["exception"] = e
            ret[0]["remark"] = "only unencrypted Speedwire is supported"
        except Exception as e:
            ret[0]["status"] = "failed"
            ret[0]["exception"] = e
        return ret

    def set_options(self, options: Dict[str, Any]):
        self._options = options
