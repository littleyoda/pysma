import logging
import re
from datetime import datetime, timedelta

_LOGGER = logging.getLogger(__name__)


class sempTimeframe:
    start: datetime
    stop: datetime
    minRunningTime: int
    maxRunningTime: int

    def __init__(
        self,
        start: datetime,
        stop: datetime,
        minRunningTime: timedelta,
        maxRunningTime: timedelta,
    ):
        self.start = start
        self.stop = stop
        self.minRunningTime = int(minRunningTime.total_seconds())
        self.maxRunningTime = int(maxRunningTime.total_seconds())
        assert self.minRunningTime >= 0
        assert self.minRunningTime <= self.maxRunningTime


class sempDevice:

    deviceId: str
    deviceName: str
    deviceType: str
    deviceSerial: str
    deviceVendor: str
    deviceMaxConsumption: int
    deviceMinConsumption: int
    timeframes: list[sempTimeframe] = []

    @staticmethod
    def possibleDeviceType():
        return [
            "Other",
            "AirConditioning",
            "Charger",
            "DishWasher",
            "Dryer",
            #                "ElectricVehicle",
            #  "EVCharger",
            "Freezer",
            "Fridge",
            "Heater",
            "HeatPump",
            "Motor",
            "Pump",
            "WashingMachine",
        ]

    def __init__(
        self,
        deviceId: str,
        deviceName: str,
        deviceType: str,
        deviceSerial: str,
        deviceVendor: str,
        maxConsumption: int,
        minConsumption: int | None = None,
        minOnTime: timedelta | None = None,
        minOffTime: timedelta | None = None,
    ):
        assert re.match(
            "F-[0-9]{8}-[0-9]{12}-00", deviceId
        ), "DeviceID does not meet the requirements "
        if not (
            len(deviceId) == 26
            and deviceId.startswith("F-11223344-")
            and deviceId.endswith("-00")
        ):
            _LOGGER.debug(
                f"DeviceID {deviceId} does not meet the recommendations: F-11223344-XXXXXXXXXXXX-00"
            )
        assert deviceType in self.possibleDeviceType()
        self.deviceId = deviceId
        self.deviceName = deviceName
        self.deviceType = deviceType
        self.deviceSerial = deviceSerial
        self.deviceVendor = deviceVendor
        self.interruptionsAllowed = False
        self.power = 0
        self.deviceMaxConsumption = maxConsumption
        self.deviceMinConsumption = (
            minConsumption if minConsumption is not None else maxConsumption
        )
        self.minOnTime = int(minOnTime.total_seconds()) if minOnTime else 120
        self.minOffTime = int(minOffTime.total_seconds()) if minOffTime else 120
        self.status = "off"
        self.optionalEnergy = False
        # is set automatically from the timeframes (true, if mintime != maxtime).
        # <OptionalEnergy>false</OptionalEnergy>

        self.emSignalsAccepted = False
        # is set automatically from the timeframes (false if no timeframe defined).
        # EMSignalsAccepted (xs:
        # Bool that indicates if the device is currently considering the control signals or recommendations
        # provided by the energy manager or if it is in a mode which ignores the signals or recommendations
        # The value should be set to “false” if there is no timeframe in the planning request sec-
        # tion for the device at the moment.

    def setPowerStatus(self, power: int, status: str):
        assert status in ["on", "off", "offline"], f"Unknown Status {status}"
        assert power >= 0
        self.status = status
        self.power = power

    def setInterruptable(self, allowinterupts: bool) -> None:
        self.interruptionsAllowed = allowinterupts

    def setTimeframes(self, timeframes: list[sempTimeframe]):
        self.timeframes = timeframes

    def addTimeframe(self, timeframe: sempTimeframe):
        assert timeframe.minRunningTime <= timeframe.maxRunningTime
        assert timeframe.minRunningTime > 0
        if timeframe.maxRunningTime == timeframe.minRunningTime:
            # workaround
            timeframe.minRunningTime -= 1
        self.timeframes.append(timeframe)

    def update(self):
        """Based on the timeframes set optionalEnergy and emSignalsAccepted"""
        # TODO sort timeframe
        # TODO Was passiert wenn emSignalsAccepted forced False + timeframes
        self.optionalEnergy = False
        for tf in self.timeframes:
            if tf.minRunningTime != tf.maxRunningTime:
                self.optionalEnergy = True
        self.emSignalsAccepted = len(self.timeframes) > 0
