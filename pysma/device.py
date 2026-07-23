"""
abstract base class on which all device implementations are based
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from .sensor import Sensor, Sensors


@dataclass
class DiscoveryInformation:
    tested_endpoints: str = ""
    status: str = ""
    access: str = ""
    exception: Exception | None = None
    remark: str = ""
    device: str = ""


@dataclass
class DeviceInformation:
    id: str
    serial: str
    name: str
    type: str
    manufacturer: str
    sw_version: str
    additional: dict[str, str | int] = field(default_factory=dict)
    measurementsCount: int | None = None
    parameterCount: int | None = None

    def asDict(self) -> dict[str, Any]:
        """Returns the values as a dict"""
        return asdict(self)

    def __str__(self):
        return f"{self.serial} {self.name}"


class Device(ABC):
    """abstract base class on which all device implementations are based."""

    @abstractmethod
    async def get_sensors(self, deviceID: str | None = None) -> Sensors:
        """Returns a list of all supported sensors"""

    @abstractmethod
    def known_sensors(self) -> list[Sensor]:
        """Return the sensors currently known to the live session, without network I/O."""

    @abstractmethod
    async def new_session(self) -> bool:
        """Starts a new session"""

    @abstractmethod
    async def device_info(self) -> dict:
        """Return a Dict with basic device information"""

    @abstractmethod
    async def device_list(self) -> dict[str, DeviceInformation]:
        """List of all devices"""

    @abstractmethod
    async def read(self, sensors: Sensors, deviceID: str | None = None) -> bool:
        """Updates all sensors"""

    @abstractmethod
    async def close_session(self) -> None:
        """Closes the session"""

    @abstractmethod
    async def detect(self, ip: str) -> List[DiscoveryInformation]:
        """Try to detect SMA devices"""

    @abstractmethod
    async def get_debug(self) -> Dict[str, Any]:
        """Return a dict with all debug information."""

    def set_options(self, options: Dict[str, Any]) -> None:
        """Set options"""
        pass

    async def set_parameter(
        self, sensor: Sensor, value: int, deviceID: str | None = None
    ) -> None:
        """Set Parameters."""
        pass
