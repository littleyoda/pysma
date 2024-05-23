"""
abstract base class on which all device implementations are based
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .sensor import Sensor, Sensors


class Device(ABC):
    """abstract base class on which all device implementations are based."""

    @abstractmethod
    async def get_sensors(self) -> Sensors:
        """Returns a list of all supported sensors"""

    @abstractmethod
    async def new_session(self) -> bool:
        """Starts a new session"""

    @abstractmethod
    async def device_info(self) -> dict:
        """Return a Dict with basic device information"""

    @abstractmethod
    async def read(self, sensors: Sensors) -> bool:
        """Updates all sensors"""

    @abstractmethod
    async def close_session(self) -> None:
        """Closes the session"""

    async def detect(self, ip: str) -> List:
        """Tries an automatic detection of this device and returns the results"""
        return [
            {
                "testedEndpoints": "",
                "status": "failed",
                "access": "",
                "device": "",
                "exception": "",
                "remark": "",
                "ip": ip,
            }
        ]

    @abstractmethod
    async def get_debug(self) -> Dict[str, Any]:
        """Return a dict with all debug information."""

    def set_options(self, options: Dict[str, Any]):
        """Set options"""
        pass

    async def handleModulActions(self):
        pass

    def set_parameter(self, sensor: Sensor | str, value: int):
        pass
