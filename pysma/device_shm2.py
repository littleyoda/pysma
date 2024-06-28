import asyncio
import copy
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ModbusResponse

from .const import Identifier, SMATagList
from .device import Device, DeviceInformation, DiscoveryInformation
from .exceptions import (
    SmaAuthenticationException,
    SmaConnectionException,
    SmaReadException,
    SmaWriteException,
)
from .helpers import isInteger, splitUrl
from .sensor import Sensor, Sensor_Range, Sensors

_LOGGER = logging.getLogger(__name__)


@dataclass
class modusbus2sensor:
    addr: int
    slaveid: int
    valueFormat: str
    sensor: Sensor
    writeonly: bool = False
    range: Sensor_Range | None = None


modusbus2sensorList: List[modusbus2sensor] = [
    # TO DO Modus readonly/writeonly/readwrite
    modusbus2sensor(
        30201,
        2,
        "u32",
        Sensor(
            Identifier.operating_status_genereal,
            Identifier.operating_status_genereal,
            factor=1,
            unit=None,
            mapper=SMATagList,
        ),
    ),
    modusbus2sensor(
        30581,
        2,
        "u32",
        Sensor(
            Identifier.metering_total_absorbed,
            Identifier.metering_total_absorbed,
            factor=1000,
            unit="kWh",
        ),
    ),
    modusbus2sensor(
        30583,
        2,
        "u32",
        Sensor(
            Identifier.metering_total_yield,
            Identifier.metering_total_yield,
            factor=1000,
            unit="kWh",
        ),
    ),
    modusbus2sensor(
        30865,
        2,
        "u32",
        Sensor(
            Identifier.metering_power_absorbed,
            Identifier.metering_power_absorbed,
            factor=1,
            unit="W",
        ),
    ),
    modusbus2sensor(
        30867,
        2,
        "u32",
        Sensor(
            Identifier.metering_power_supplied,
            Identifier.metering_power_supplied,
            factor=1,
            unit="W",
        ),
    ),
    modusbus2sensor(
        40151,
        2,
        "u32",
        Sensor(
            Identifier.operating_mode_plant_control,
            Identifier.operating_mode_plant_control,
            factor=1,
            unit=None,
            mapper=SMATagList,
        ),
        True,
        range=Sensor_Range("selection", [802, 803], True, SMATagList),
    ),
    modusbus2sensor(
        40149,
        2,
        "s32",
        Sensor(
            Identifier.power_setpoint_plant_control,
            Identifier.power_setpoint_plant_control,
            factor=1,
            unit="W",
        ),
        True,
        range=Sensor_Range("min/max", [-100000, 100000], True),
    ),
]
modbusDict = {i.sensor.key: i for i in modusbus2sensorList}


class SHM2(Device):
    """ """

    def __init__(self, ip: str, password: str | None):
        """Init"""
        destination = splitUrl(ip)
        _LOGGER.debug(f"{destination}")
        self._ip = destination["host"]
        self._sensorValues: Dict[str, int] = {}
        if password:
            if not isInteger(password):
                raise SmaConnectionException(
                    "Password/Grid Guard Code must be a number."
                )
            self._ggc = int(password)
        else:
            self._ggc = 0
        self._device_list: Dict[str, DeviceInformation] = {}
        self._client: AsyncModbusTcpClient

    async def get_sensors(self, deviceID: str | None = None) -> Sensors:
        """Returns a list of all supported sensors"""
        device_sensors = Sensors()
        for s in modusbus2sensorList:
            device_sensors.add(copy.copy(s.sensor))
        return device_sensors

    async def _login(self):
        """Login Using Grid Guard Code"""
        _LOGGER.debug("Login with GGC")
        ret = await self._client.write_registers(
            43090, [self._ggc // 65536, self._ggc % 65536], slave=1
        )
        _LOGGER.debug(f"Login-Response {ret}")
        print("Login-Response", ret)
        # Exception Response(144, 16, IllegalValue)
        # WriteMultipleRegisterResponse
        await asyncio.sleep(2)

    async def _read_sensor(self, sensorDef: modusbus2sensor):
        """Read a modbus register based on the sensorDefinition"""
        return await self.read_modbus(
            sensorDef.addr, sensorDef.slaveid, sensorDef.valueFormat
        )

    async def read_modbus(self, register: int, slave: int, number_format: str) -> int:
        """Read from modbus"""
        try:
            ret = await self._client.read_holding_registers(register, 2, slave=slave)
        except ModbusException as exc:
            _LOGGER.error(exc)
            raise SmaConnectionException(f"ERROR: exception in pymodbus {exc}") from exc
        if ret.isError():
            _LOGGER.error(f"ERROR: pymodbus returned an error! {ret}")
            raise SmaReadException(f"Modbus {register} Slave:{slave} Count: 2")
        if number_format.lower() == "u32":
            return ret.registers[0] * (2**16) + ret.registers[1]
        else:
            raise ValueError(f"Unsupported format {number_format}")

    async def new_session(self) -> bool:
        """Starts a new session"""

        self._client = AsyncModbusTcpClient(str(self._ip))  # Create client object
        connected = await self._client.connect()
        if not connected:
            raise SmaConnectionException(f"Could not connect to {self._ip}:502")

        device = await self.read_modbus(30053, 1, "u32")
        if device != 9343:
            raise SmaConnectionException(f"No Sunny Home Manager 2 found. ({device})")

        ggcStatus = await self.read_modbus(43090, 1, "u32")
        _LOGGER.debug(f"GGC Code {ggcStatus}")
        if ggcStatus == 0:
            await self._login()
        ggcStatus = await self.read_modbus(43090, 1, "u32")
        _LOGGER.debug(f"After Login -- GGC Code {ggcStatus}")
        if ggcStatus == 0:
            raise SmaAuthenticationException("Grid Guard Code is not valid!")
        return True

    async def device_info(self) -> dict:
        """Read device info and return the results.

        Returns:
            dict: dict containing serial, name, type, manufacturer and sw_version
        """
        di = await self.device_list()
        return list(di.values())[0].asDict()

    def _u32(self, regs: ModbusResponse) -> int:
        #        print(regs.registers)
        return regs.registers[0] * (2**16) + regs.registers[1]

    async def device_list(self) -> dict[str, DeviceInformation]:
        """List of all devices"""
        self._device_list = {}
        serial = str(await self.read_modbus(30005, 1, "u32"))
        device = await self.read_modbus(30053, 1, "u32")
        vendor = await self.read_modbus(30055, 1, "u32")
        deviceName = SMATagList.get(device, f"Unknown Device {device}")
        vendorName = SMATagList.get(vendor, f"Unknown Vendor {vendor}")
        self._device_list[serial] = DeviceInformation(
            serial, serial, deviceName, deviceName, vendorName, ""
        )
        return self._device_list

    async def read(self, sensors: Sensors, deviceID: str | None = None) -> bool:
        """Updates all sensors"""
        notfound = []
        for sensor in sensors:
            #            print(sensor)
            if sensor.key not in modbusDict:
                notfound.append(sensor.key)
                continue
            sensorDef = modbusDict[sensor.key]
            value = None
            if not sensorDef.writeonly:
                value = await self._read_sensor(sensorDef)
                if sensor.factor and sensor.factor != 1:
                    value = round(value / sensor.factor, 4)
                sensor.value = value
                if sensor.mapper:
                    sensor.mapped_value = sensor.mapper.get(value, str(value))
            else:
                if sensor.key in self._sensorValues:
                    sensor.value = self._sensorValues[sensor.key]
                else:
                    sensor.value = None
            if sensorDef.range:
                sensor.range = sensorDef.range

        # if notfound:
        #     _LOGGER.info(
        #         "No values for sensors: %s",
        #         ",".join(notfound),
        #     )

        return True

    async def close_session(self) -> None:
        """Closes the session"""

    async def detect(self, ip: str) -> List[DiscoveryInformation]:
        """Try to detect SMA devices"""
        rets = []
        try:
            di = DiscoveryInformation()
            rets.append(di)
            di.tested_endpoints = ip
            di.remark = "needs Grid Guard Code"

            self._client = AsyncModbusTcpClient(str(self._ip))
            connected = await self._client.connect()
            if not connected:
                raise SmaConnectionException(f"Could not connect to {self._ip}:502")

            device = await self.read_modbus(30053, 1, "u32")
            if device != 9343:
                raise SmaConnectionException(
                    f"No Sunny Home Manager 2 found. ({device})"
                )
            di.status = "found"
            di.exception = None
        except Exception as e:  # pylint: disable=broad-exception-caught
            di.status = "failed"
            di.exception = e
        return rets

    async def get_debug(self) -> Dict[str, Any]:
        """Return a dict with all debug information."""
        return {}

    def set_options(self, options: Dict[str, Any]) -> None:
        """Set options"""

    async def set_parameter(
        self, sensor: Sensor, value: int, deviceID: str | None = None
    ) -> None:
        """Set Parameters."""
        if sensor.key not in modbusDict:
            raise SmaWriteException(f"Can not write to sensor {sensor.key}")
        info = modbusDict[sensor.key]
        if not info.writeonly:
            raise SmaWriteException(f"Not allowed to write to the sensor {sensor.key}")
        key = info.sensor.key
        if info.valueFormat == "u32":
            b = value.to_bytes(4, byteorder="big")
            values = [b[0] * 256 + b[1], b[2] * 256 + b[3]]
        elif info.valueFormat == "s32":
            b = value.to_bytes(4, byteorder="big", signed=True)
            values = [b[0] * 256 + b[1], b[2] * 256 + b[3]]
        else:
            raise SmaWriteException(
                f"Unsupported Format {info.valueFormat} for writing."
            )
        try:
            ret = await self._client.write_registers(
                info.addr, values, slave=info.slaveid
            )
        except ModbusException as exc:
            _LOGGER.error(exc)
            raise SmaWriteException(f"Error writing to sensor {sensor.key}") from exc
        if ret.isError():
            raise SmaWriteException(f"Error writing to sensor {sensor.key} {ret}")
        if info.writeonly:
            self._sensorValues[key] = value
