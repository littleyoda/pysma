"""Async adapter for SMA Speedwire inverters (unencrypted protocol).
   parts taken from https://github.com/eddso/ha_sma_speedwire/blob/main/custom_components/sma_speedwire/sma_speedwire.py """
from __future__ import annotations

import asyncio
import copy
import logging
import struct
import time
from dataclasses import dataclass
from struct import unpack_from
from typing import Any, Dict, List, Optional

from .definitions_speedwire import (
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


MY_SYSTEMID = 0x00ED
MY_SERIAL = 0x23021922
ANY_SYSTEMID = 0xFFFF
ANY_SERIAL = 0xFFFFFFFF
SMA_PKT_HEADER = "534D4100000402A000000001"
SMA_ESIGNATURE = "00106065"

sensorList = [
    "TypeLabel",
    "PVEnergyProduction",
    "EnergyProduction",
    "SpotDCPower",
    "SpotDCPower_3",
    "SpotACTotalPower",
    "ChargeStatus",
    "SpotDCVoltage",
    "SpotACCurrentBackup",
    "BatteryInfo_TEMP",
    "BatteryInfo_UDC",
    "BatteryInfo_IDC",
    "BatteryInfo_Charge",
    "BatteryInfo_Capacity",
    "BatteryInfo",
    "BatteryInfo_3",
    "BatteryInfo_4",
    "BatteryInfo_5",
    "SpotGridFrequency",
    "OperationTime",
    "InverterTemperature",
]


class _SpeedwireProtocol(asyncio.DatagramProtocol):
    """UDP protocol helper that exposes awaited responses."""

    def __init__(self, loop: asyncio.AbstractEventLoop, logger: logging.Logger):
        """Store loop and logger references used for UDP communication."""
        self._loop = loop
        self._logger = logger
        self.transport: asyncio.transports.DatagramTransport | None = None
        self._response_future: asyncio.Future[bytes] | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Remember the transport once the datagram endpoint is ready."""
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Resolve the pending waiter with the received payload."""
        self._logger.debug("< %s", data.hex())
        if self._response_future and not self._response_future.done():
            self._response_future.set_result(data)

    def error_received(self, exc: Exception | None) -> None:
        """Propagate socket errors to the awaiting coroutine."""
        if self._response_future and not self._response_future.done():
            self._response_future.set_exception(exc or ConnectionError("UDP error"))

    def connection_lost(self, exc: Exception | None) -> None:
        """Handle transport shutdown by rejecting waiters."""
        if self._response_future and not self._response_future.done():
            self._response_future.set_exception(
                exc or ConnectionError("Connection lost")
            )
        self.transport = None

    async def request(
        self, payload: bytes, timeout: float, expect_response: bool
    ) -> bytes:
        """Send one UDP datagram and optionally wait for a reply."""
        if self.transport is None:
            raise ConnectionError("Transport not connected")
        if expect_response:
            if self._response_future is not None and not self._response_future.done():
                self._response_future.cancel()
            self._response_future = self._loop.create_future()
        self.transport.sendto(payload)
        if not expect_response:
            self._response_future = None
            return b""
        try:
            return await asyncio.wait_for(self._response_future, timeout=timeout)
        finally:
            self._response_future = None


@dataclass
class _SessionState:
    serial: int | None = None
    inv_class: str | None = None
    inv_type: str | None = None


class _AsyncSpeedwireSession:
    """Asynchronous version of the legacy Speedwire client."""

    sensors: Dict[str, Sensor] = {}
    data_values = {}

    def __init__(self, host: str, password: str, logger: logging.Logger):
        """Prepare session state; actual network setup is deferred."""
        self.host = host
        self.port = 9522
        self.password = password
        self.logger = logger
        self.retry = 2
        self.timeout = 3.0

        self._loop: asyncio.AbstractEventLoop | None = None
        self._transport: asyncio.transports.DatagramTransport | None = None
        self._protocol: _SpeedwireProtocol | None = None
        self._initialized = False

        self.pkt_id = 0
        self.my_id = MY_SYSTEMID.to_bytes(2, "little") + MY_SERIAL.to_bytes(4, "little")
        self.target_id = ANY_SYSTEMID.to_bytes(2, "little") + ANY_SERIAL.to_bytes(
            4, "little"
        )
        self.state = _SessionState()

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
                if not overwrite:
                    value = oldValue
        self.sensors[sen.key] = sen
        self.data_values[sen.key] = value

    async def ensure_initialized(self) -> None:
        """Ensure a login has happened and static metadata is cached."""
        if self._initialized:
            return
        await self.init()
        self._initialized = True

    async def init(self) -> None:
        """Run the initial login/info/logout handshake."""
        await self._login()
        await self._fetch("TypeLabel")
        await self._logout()

    async def update(self) -> None:
        """Fetch current energy and power metrics."""
        await self._login()
        for sensorName in sensorList:
            await self._fetch(sensorName)
        await self._logout()

    def apply_options(self, options: Dict[str, Any]) -> None:
        """Update retry/timeout configuration from user options."""
        retries = options.get("retries")
        if isinstance(retries, int) and retries > 0:
            self.retry = retries
        timeout = options.get("timeout")
        if timeout is not None:
            try:
                self.timeout = float(timeout)
            except (TypeError, ValueError):
                self.logger.debug("Ignoring invalid timeout option: %s", timeout)

    async def close(self) -> None:
        """Close the underlying datagram endpoint."""
        if self._transport:
            self._transport.close()
        self._transport = None
        self._protocol = None
        self._initialized = False

    async def _ensure_transport(self) -> None:
        """Create a UDP transport when required."""
        if self._transport is not None:
            return
        self._loop = asyncio.get_running_loop()
        transport, protocol = await self._loop.create_datagram_endpoint(
            lambda: _SpeedwireProtocol(self._loop, self.logger),
            remote_addr=(self.host, self.port),
        )
        self._transport = transport  # type: ignore[assignment]
        self._protocol = protocol

    def _create_request_packet(self, cmd: str) -> bytes:
        """Build a protocol packet for the requested command name."""
        self.pkt_id += 1
        cmdDef = commands[cmd]
        if not cmdDef:
            print(f"Command {cmd} not found! {cmdDef}")
            raise SmaReadException("Command not found!")
        command = cmdDef["command"]
        first = cmdDef["first"]
        last = cmdDef["last"]
        sep2 = bytes([0x00, 0x00])
        sep4 = bytes([0x00, 0x00, 0x00, 0x00])
        data = sep4
        esignature = bytes.fromhex(SMA_ESIGNATURE + "09A0")

        if cmd == "login2":
            sep2 = bytes([0x00, 0x01])
            esignature = bytes.fromhex(SMA_ESIGNATURE + "0EA0")
            encpasswd = [0x88] * 12
            passwd_bytes = [((0x88 + ord(char)) & 0xFF) for char in self.password]
            encpasswd[0 : len(passwd_bytes)] = passwd_bytes
            data = int(time.time()).to_bytes(4, "little")
            data += sep4 + bytes(encpasswd) + sep4
        elif cmd == "logoff":
            sep2 = bytes([0x00, 0x03])
            esignature = bytes.fromhex(SMA_ESIGNATURE + "08A0")
            data = bytes([])

        msg = bytes.fromhex(SMA_PKT_HEADER) + bytes([0x00, 0x00]) + esignature
        msg += self.target_id + sep2 + self.my_id + sep2
        msg += sep4 + (self.pkt_id | 0x8000).to_bytes(2, "little")
        msg += command.to_bytes(4, "little")
        msg += first.to_bytes(4, "little")
        msg += last.to_bytes(4, "little")
        msg += data
        pkt_len = (len(msg) - 20).to_bytes(2, "big")
        msg = msg[:12] + pkt_len + msg[14:]
        return msg

    async def _send_receive(self, cmd: str, receive: bool = True) -> bytes:
        """Send a command and optionally wait for the inverter response."""
        await self._ensure_transport()
        assert self._protocol is not None
        attempt = 0
        last_exc: Exception | None = None
        while attempt < self.retry:
            attempt += 1
            msg = self._create_request_packet(cmd)
            self.logger.debug("> %s", msg.hex())
            try:
                data = await self._protocol.request(
                    msg, timeout=self.timeout, expect_response=receive
                )
                if not receive:
                    return b""
                size = len(data)
                if size <= 42:
                    raise SmaReadException("Format of inverter response does not fit.")
                pkt_id = unpack_from("H", data, offset=40)[0] & 0x7FFF
                error = unpack_from("I", data, offset=36)[0]
                if error != 0:
                    self.logger.debug(
                        "Req/Rsp: Packet ID %X/%X, Error %d",
                        self.pkt_id,
                        pkt_id,
                        error,
                    )
                    if cmd == "login2" and error == 256:
                        raise SmaAuthenticationException(
                            "Login failed! Credentials wrong (user/install or password)"
                        )
                    return None
                if pkt_id != self.pkt_id:
                    self.pkt_id = pkt_id
                return data
            except (asyncio.TimeoutError, ConnectionError) as exc:
                self.logger.error("Timeout in repeat %i/%i", attempt, self.retry)
                last_exc = exc
            except (SmaAuthenticationException, SmaReadException):
                raise

        raise SmaConnectionException("No response from inverter") from last_exc

    async def _login(self) -> None:
        """Send the login packet and remember the inverter ids."""
        data = await self._send_receive("login2")
        if not data:
            raise SmaConnectionException("Login failed: no response")
        inv_susyid, inv_serial = unpack_from("<HI", data, offset=28)
        self.state.serial = inv_serial
        self.target_id = inv_susyid.to_bytes(2, "little") + inv_serial.to_bytes(
            4, "little"
        )
        self.logger.debug(
            "Logged in to inverter susyid: %d, serial: %d", inv_susyid, inv_serial
        )

    async def _logout(self) -> None:
        """Attempt to end the session gracefully."""
        try:
            await self._send_receive("logoff", receive=False)
        except SmaConnectionException:
            # Logout failures are non-fatal.
            self.logger.debug("Logout failed, ignoring.")
        self.pkt_id = 0

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

    async def _fetch(self, command: str) -> None:
        """Decode inverter responses for the given command."""
        data = await self._send_receive(command)
        if not data:
            return
        # Check if message is a 6065 protocol
        msg = speedwireHeader.from_packed(data[0:18])
        if not msg.check6065():
            _LOGGER.debug("Ignoring non 6065 Response. %d", msg.protokoll)
            return

        # If the requested information is not available, send the next command,
        if len(data) < 58:
            _LOGGER.debug(f"NACK [{len(data)}] -- {data!r}")
            #  self._confirm_repsonse()
            return

        msg6065 = speedwireHeader6065.from_packed(data[18 : 18 + 36])
        # Handle Login Responses
        # TODO Should not happen in this implementation
        # if msg6065.isLoginResponse():
        #     self.handle_login(msg6065)
        #     self._confirm_repsonse()
        #     return
        (cnt_registers, size_registers) = self.calc_register(data, msg6065)
        code = int.from_bytes(data[54:58], "little")
        codem = code & 0x00FFFF00
        if len(data) == 58 and codem == 0:
            _LOGGER.debug(f"NACK [{len(data)}] -- {data!r}")
            return
        if size_registers <= 0 or size_registers not in [16, 28, 40]:
            _LOGGER.warning(
                f"Skipping message. --- Len {data!r} Ril {codem} {cnt_registers} x {size_registers} bytes"
            )
            return

        # Extract the values for each register
        for idx in range(0, cnt_registers):
            start = idx * size_registers + 54
            self.handle_register(data[start : start + size_registers], idx)

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
        # self.debug["ids"].add(c[6:])
        # self._id = c[6:]
        c = self.fixID(c)

        # Handle unknown Responses
        if c not in responseDef:
            values = []
            valuesPos = []
            for idx in range(8, len(subdata), 4):
                v = struct.unpack("<l", subdata[idx : idx + 4])[0]
                values.append(v)
                valuesPos.append(f"{idx + 54}")
                return

            _LOGGER.debug(f"No Handler for {c}: {values} @ {valuesPos}")
            # TODO
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
            self.handle_newvalue(sensor, v, handler.get("overwrite", True))

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


class SMAspeedwireINVV2(Device):
    """Async Device implementation for Speedwire inverters."""

    def __init__(self, host: str, group: str, password: Optional[str]):
        """Initialise wrapper with connection parameters."""
        if group not in ["user", "installer"]:
            raise KeyError(f"Invalid user type: {group} (user or installer)")
        self._host = host
        self._group = group
        self._password = password or "0000"

        self._session: _AsyncSpeedwireSession | None = None
        self._deviceinfo: DeviceInformation | None = None
        self._device_list: Dict[str, DeviceInformation] = {}
        self._last_values: Dict[str, Any] = {}
        self._options: Dict[str, Any] = {}

        self._logger = logging.getLogger(__name__).getChild("speedwirev2")

    def _create_session(self) -> _AsyncSpeedwireSession:
        """Construct a fresh async session with current options."""
        session = _AsyncSpeedwireSession(self._host, self._password, self._logger)
        session.apply_options(self._options)
        return session

    async def _ensure_session(self) -> _AsyncSpeedwireSession:
        """Return an active session, creating one if needed."""
        if self._session is None:
            self._session = self._create_session()
        return self._session

    def _update_device_info(self, session: _AsyncSpeedwireSession) -> None:
        """Convert session metadata into the public DeviceInformation format."""
        if session.state.serial is None:
            raise SmaConnectionException("No inverter serial received")
        serial = str(session.state.serial)
        inv_type = session.state.inv_type or "SMA Speedwire Inverter"
        inv_class = session.state.inv_class or "Speedwire Device"
        self._deviceinfo = DeviceInformation(
            serial, serial, inv_type, inv_class, "SMA", ""
        )
        self._device_list = {serial: self._deviceinfo}

    async def new_session(self) -> bool:
        """Open a connection and validate credentials."""
        session = await self._ensure_session()
        await session.ensure_initialized()
        self._update_device_info(session)
        return True

    # @override
    async def get_sensors(self, deviceID: str | None = None) -> Sensors:  # noqa: ARG002
        """Return the static sensor definitions supported by this inverter."""
        session = await self._ensure_session()
        await session.ensure_initialized()
        await session.update()
        sensors = Sensors()
        for s in session.sensors.values():
            sensors.add(s)
        return sensors

    async def device_info(self) -> dict:
        """Expose the cached DeviceInformation structure as a dict."""
        await self.new_session()
        return self._deviceinfo.asDict() if self._deviceinfo else {}

    async def device_list(self) -> dict[str, DeviceInformation]:
        """List known devices (only the inverter itself for this adapter)."""
        await self.new_session()
        return self._device_list

    async def read(
        self, sensors: Sensors, deviceID: str | None = None
    ) -> bool:  # noqa: ARG002
        """Populate the provided Sensors collection with fresh values."""
        session = await self._ensure_session()
        try:
            await session.update()
        except SmaConnectionException as exc:
            raise SmaReadException(str(exc)) from exc

        for sen in sensors:
            if sen.enabled and sen.key in session.sensors:
                value = session.sensors[sen.key].value
                if sen.mapper:
                    sen.mapped_value = sen.mapper.get(value, str(value))
                sen.value = value
        return True

    async def close_session(self) -> None:
        """Tear down any active session state."""
        if self._session:
            await self._session.close()
        self._session = None

    async def detect(self, ip: str) -> List[DiscoveryInformation]:
        """Probe the given IP for a compatible Speedwire inverter."""
        discovery = DiscoveryInformation()
        discovery.tested_endpoints = f"{ip}:9522"
        session = _AsyncSpeedwireSession(ip, self._password, self._logger)
        session.apply_options(self._options)
        try:
            await session.ensure_initialized()
            discovery.status = "ok"
            discovery.device = session.state.inv_type
            discovery.remark = "using default pwd 0000"
        except SmaAuthenticationException as exc:
            discovery.status = "maybe"
            discovery.exception = exc
            discovery.remark = "only unencrypted Speedwire is supported"
        except (SmaConnectionException, SmaReadException) as exc:
            discovery.status = "failed"
            discovery.exception = exc
        finally:
            await session.close()
        return [discovery]

    async def get_debug(self) -> Dict[str, Any]:
        """Return internal debug information for troubleshooting."""
        session = await self._ensure_session()
        await session.ensure_initialized()
        return {
            "device_info": self._deviceinfo.asDict() if self._deviceinfo else None,
            "last_values": self._last_values.copy(),
            "inverter_type": session.state.inv_type,
            "inverter_class": session.state.inv_class,
        }

    def set_options(self, options: Dict[str, Any]) -> None:
        """Update adapter options and push them to the active session."""
        self._options = options or {}
        if self._session:
            self._session.apply_options(self._options)
