from datetime import datetime, timedelta


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
        assert self.minRunningTime > 0
        assert self.minRunningTime <= self.maxRunningTime


class sempDevice:

    deviceId: str
    deviceName: str
    deviceType: str
    deviceSerial: str
    deviceVendor: str
    deviceMaxConsumption: int
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
    ):
        assert (
            len(deviceId) == 26
            and deviceId.startswith("F-11223344-")
            and deviceId.endswith("-00")
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
        self.status = "off"
        self.optionalEnergy = False
        # true, falls mintime != maxtime
        # <OptionalEnergy>false</OptionalEnergy>

        self.emSignalsAccepted = False
        # EMSignalsAccepted (xs:
        # Bool that indicates if the device is currently considering the control signals or recommendations
        # provided by the energy manager or if it is in a mode which ignores the signals or recommendations
        # The value should be set to “false” if there is no timeframe in the planning request sec-
        # tion for the device at the moment.

    def setPowerStatus(self, power: int, status: str):
        assert status in ["on", "off", "offline"]
        assert power >= 0
        self.status = status
        self.power = power

        # Optional i Device Info

    # <MinOnTime>1200</MinOnTime>
    # <MinOffTime>600</MinOffTime>

    def setTimeframes(self, timeframes: list[sempTimeframe]):
        self.timeframes = timeframes

    def addTimeframe(self, timeframe: sempTimeframe):
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


# <PlanningRequest>
# <Timeframe>
# <DeviceId>F-11223344-112233445566-00</DeviceId>
# <EarliestStart>0</EarliestStart><!-- already running -->
# <LatestEnd>10800</LatestEnd><!—latest end in 3h -->
# <!-- mandatory demand of 0.5h (MinRunningTime = MaxRunningTime) -->
# <MinRunningTime>1800</MinRunningTime>
# <MaxRunningTime>1800</MaxRunningTime>
# <PreferenceIndifferentAreas>Late</PreferenceIndifferentAreas>
# </Timeframe>
# <Timeframe>
# <DeviceId>F-11223344-112233445566-00</DeviceId>
# <EarliestStart>18000</EarliestStart><!-- earliest start in 5h -->
# <LatestEnd>25200</LatestEnd><!-- latest end in 7h -->
# <!-- optional runtime of 30min (MinRunningTime=0) -->
# <MinRunningTime>0</MinRunningTime>
# <MaxRunningTime>1800</MaxRunningTime>
# </Timeframe>
# </PlanningRequest>
