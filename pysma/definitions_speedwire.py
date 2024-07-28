"""Implementation for SMA Speedwire

Originally based on https://github.com/Wired-Square/sma-query/blob/main/src/sma_query_sw/commands.py
Improved with Information from https://github.com/mhop/fhem-mirror/blob/master/fhem/FHEM/76_SMAInverter.pm
Receiver classes completely reimplemented by little.yoda
"""

# pylint: disable=too-many-lines

import ctypes
import time
from ctypes import LittleEndianStructure
from typing import Annotated, Any, Dict

import dataclasses_struct as dcs

from .const import Identifier, SMATagList
from .sensor import Sensor

responseDef: dict[str, list[dict[str, Any]]] = {
    "00464B01": [],  # Netzspannung Phase L1 gegen L2
    "00464C01": [],  # Netzspannung Phase L2 gegen L3
    "00464D01": [],  # Netzspannung Phase L3 gegen L1
    "00416601": [],  # WaitingTimeUntilFeedIn  WaitingTimeUntilFeedIn
    "00411E01": [],  # MaxACPower
    "00411F01": [],  # MaxACPower
    "00412001": [],  # MaxACPower
    "00462E01": [],  # OperationTime
    "00462F01": [],  # OperationTime
    "00823401": [
        {
            "cmd": "Firmware",
            "format": "version",
            "sensor": Sensor("Firmware", Identifier.device_sw_version),
            "idx": 4,
            "overwrite": False,
        }
    ],
    "00260101": [
        {
            "cmd": "EnergyProduction",
            "format": "uint",
            "sensor": Sensor("total", Identifier.total_yield, factor=1000, unit="kWh"),
            "idx": 0,
        }
    ],
    "40251E01": [
        {
            "cmd": "SpotDCPower",
            "format": "uint",
            "sensor": Sensor(
                "spot_dc_power1", Identifier.pv_power_a, factor=1, unit="W"
            ),
            "idx": 0,
        }
    ],
    "40251E02": [
        {
            "cmd": "SpotDCPower",
            "format": "uint",
            "sensor": Sensor(
                "spot_dc_power2", Identifier.pv_power_b, factor=1, unit="W"
            ),
            "idx": 0,
        }
    ],
    "40251E03": [
        {
            "cmd": "SpotDCPower",
            "format": "uint",
            "sensor": Sensor(
                "spot_dc_power3", Identifier.pv_power_c, factor=1, unit="W"
            ),
            "idx": 0,
        }
    ],
    "40464001": [
        {
            "cmd": "spot_ac_power",
            "format": "int",
            "sensor": Sensor("spot_ac_power1", Identifier.power_l1, factor=1, unit="W"),
            "idx": 0,
        }
    ],
    "40464101": [
        {
            "cmd": "spot_ac_power",
            "format": "int",
            "sensor": Sensor("spot_ac_power2", Identifier.power_l2, factor=1, unit="W"),
            "idx": 0,
        }
    ],
    "40464201": [
        {
            "cmd": "spot_ac_power",
            "format": "int",
            "sensor": Sensor("spot_ac_power3", Identifier.power_l3, factor=1, unit="W"),
            "idx": 0,
        }
    ],
    "08412801": [
        {
            "cmd": "OperatingStatus",
            "format": "uint",
            "sensor": [
                Sensor(
                    "GeneralOperatingStatus",
                    Identifier.operating_status_genereal,
                    factor=1,
                    mapper=SMATagList,
                ),
                Sensor(
                    "GeneralOperatingStatus2",
                    "Temp GeneralOperatingStatus2",
                    factor=1,
                    mapper=SMATagList,
                ),
            ],
            "idx": 0xFF,
        }
    ],
    "0046C201": [
        {
            "cmd": "SpotDCPower_3",
            "format": "uint",
            "sensor": Sensor("pv_power", Identifier.pv_power, unit="W"),
            "idx": 0,
        }
    ],
    "40263F01": [
        {
            "cmd": "SpotACTotalPower",
            "format": "int",
            "sensor": Sensor("grid_power", Identifier.grid_power, unit="W"),
            "idx": 0,
        }
    ],
    "00464801": [
        {
            "cmd": "spot_ac_voltage",
            "format": "uint",
            "sensor": Sensor(
                "spot_ac_voltage1", Identifier.voltage_l1, factor=100, unit="V"
            ),
            "idx": 0,
        }
    ],
    "00464901": [
        {
            "cmd": "spot_ac_voltage",
            "format": "uint",
            "sensor": Sensor(
                "ac_voltage_l1", Identifier.voltage_l2, factor=100, unit="V"
            ),
            "idx": 0,
        }
    ],
    "00464A01": [
        {
            "cmd": "spot_ac_voltage",
            "format": "uint",
            "sensor": Sensor(
                "ac_voltage_l2", Identifier.voltage_l3, factor=100, unit="V"
            ),
            "idx": 0,
        }
    ],
    "40465301": [
        {
            "cmd": "spot_ac_voltage",
            "format": "uint",
            "sensor": Sensor(
                "ac_current_l1", Identifier.current_l1, factor=1000, unit="A"
            ),
            "idx": 0,
        }
    ],
    "40465401": [
        {
            "cmd": "spot_ac_voltage",
            "format": "uint",
            "sensor": Sensor(
                "ac_current_l2", Identifier.current_l2, factor=1000, unit="A"
            ),
            "idx": 0,
        }
    ],
    "40465501": [
        {
            "cmd": "spot_ac_voltage",
            "format": "uint",
            "sensor": Sensor(
                "ac_current_l3", Identifier.current_l3, factor=1000, unit="A"
            ),
            "idx": 0,
        }
    ],
    "08412B01": [
        {
            "cmd": "OperatingStatus",
            "format": "uint",
            "sensor": Sensor(
                "OperatingStatus", Identifier.operating_status, mapper=SMATagList
            ),
            "idx": 0xFF,
        }
    ],
    "0046C301": [
        {
            "cmd": "PVEnergyProduction",
            "format": "uint",
            "sensor": Sensor(
                "pvEnergyProduction", Identifier.pv_gen_meter, unit="kWh", factor=1000
            ),
            "idx": 0,
        }
    ],
    "0846A601": [
        {
            "cmd": "GridConection",
            "format": "uint",
            #                "sensor": , TODO
            "idx": 0xFF,
        }
    ],
    "08214801": [
        {
            "cmd": "DeviceStatus",
            "format": "uint",
            "sensor": Sensor("inverter_status", Identifier.status, mapper=SMATagList),
            "idx": 0xFF,
        }
    ],
    "40451F01": [
        {
            "cmd": "SpotACCurrent",
            "format": "uint",
            "sensor": Sensor(
                "spot_dc_voltage1", Identifier.pv_voltage_a, factor=100, unit="V"
            ),
            "idx": 0,
        }
    ],
    "40451F02": [
        {
            "cmd": "SpotACCurrent",
            "format": "uint",
            "sensor": Sensor(
                "spot_dc_voltage2", Identifier.pv_voltage_b, factor=100, unit="V"
            ),
            "idx": 0,
        }
    ],
    "40451F03": [
        {
            "cmd": "SpotACCurrent",
            "format": "uint",
            "sensor": Sensor(
                "spot_dc_voltage3", Identifier.pv_voltage_c, factor=100, unit="V"
            ),
            "idx": 0,
        }
    ],
    "40452101": [
        {
            "cmd": "SpotACCurrent",
            "format": "uint",
            "sensor": Sensor(
                "spot_dc_current1", Identifier.pv_current_a, factor=1000, unit="A"
            ),
            "idx": 0,
        }
    ],
    "40452102": [
        {
            "cmd": "SpotACCurrent",
            "format": "uint",
            "sensor": Sensor(
                "spot_dc_current2", Identifier.pv_current_b, factor=1000, unit="A"
            ),
            "idx": 0,
        }
    ],
    "40452103": [
        {
            "cmd": "SpotACCurrent",
            "format": "uint",
            "sensor": Sensor(
                "spot_dc_current3", Identifier.pv_current_c, factor=1000, unit="A"
            ),
            "idx": 0,
        }
    ],
    "08416401": [
        {
            "cmd": "GridRelayStatus",
            "format": "uint",
            "sensor": Sensor(
                "GridRelayStatus", Identifier.grid_relay_status, mapper=SMATagList
            ),
            "idx": 0xFF,
        }
    ],
    "00465701": [
        {
            "cmd": "SpotGridFrequency",
            "format": "uint",
            "sensor": Sensor(
                "grid_frequency", Identifier.frequency, factor=100, unit="Hz"
            ),
            "idx": 0,
        }
    ],
    "10821E01": [
        {
            "cmd": "TypeLabel",
            "format": "uint",
            # "sensor": TODO Vermutlich String
            "idx": 0,
        }
    ],
    "08821F01": [
        {
            "cmd": "TypeLabel",
            "format": "uint",
            "sensor": Sensor(
                "inverter_class", Identifier.device_class, mapper=SMATagList
            ),
            "idx": 0xFF,
            "overwrite": False,
        }
    ],
    "08822001": [
        {
            "cmd": "TypeLabel",
            "format": "uint",
            "sensor": Sensor(
                "inverter_type", Identifier.device_type, mapper=SMATagList
            ),
            "idx": 0xFF,
            "overwrite": False,
        }
    ],
    "00262201": [
        {
            "cmd": "energy_production",
            "format": "uint",
            "sensor": Sensor("today", Identifier.daily_yield, unit="Wh"),
            "idx": 0,
        }
    ],
    "00254F01": [
        {
            "cmd": "",
            "format": "uint",
            "sensor": Sensor(
                "Insulation_2",
                Identifier.pv_isolation_resistance,
                unit="kOhm",
                factor=1000,
            ),
            "idx": 0,
        }
    ],
    "40254E01": [
        {
            "cmd": "",
            "format": "uint",
            "sensor": Sensor(
                "Insulation_1",
                Identifier.insulation_residual_current,
                unit="mA",
            ),
            "idx": 0,
        }
    ],
    "00462401": [
        {
            "cmd": "EM_1",
            "format": "uint",
            "sensor": Sensor(
                "meter_yield",
                Identifier.metering_total_yield,
                unit="kWh",
                factor=1000,
            ),
            "idx": 0,
        }
    ],
    "40237701": [
        {
            "cmd": "InverterTemperature",
            "format": "uint",
            "sensor": Sensor(
                "InverterTemperature",
                Identifier.temp_a,
                unit="°C",
                factor=100,
            ),
            "idx": 0,
        }
    ],
    "00295A01": [
        {
            "cmd": "ChargeStatus",
            "format": "uint",
            "sensor": Sensor("ChargeStatus", Identifier.battery_soc_total, unit="%"),
            "idx": 0,
        }
    ],
    "40491E01": [
        {
            "cmd": "BatteryInfo",
            "format": "uint",
            "sensor": Sensor("TEMP BAT_CYCLES", "TEMP Battery Cycles"),
            "idx": 0,
        }
    ],
    "40495B01": [
        {
            "cmd": "batteryTemp",
            "format": "uint",
            "sensor": Sensor(
                "batteryTemp",
                Identifier.battery_temp_a,
                unit="°C",
                factor=10,
            ),
            "idx": 0,
        }
    ],
    "00496701": [
        {
            "cmd": "SpotBatteryLoad",
            "format": "uint",
            "sensor": Sensor(
                "SpotBatteryLoad",
                Identifier.battery_charge_total,
                unit="kWh",
                factor=1000,
            ),
            "idx": 0,
        }
    ],
    "00496801": [
        {
            "cmd": "SpotBatteryUnload",
            "format": "uint",
            "sensor": Sensor(
                "SpotBatteryUnLoad",
                Identifier.battery_discharge_total,
                unit="kWh",
                factor=1000,
            ),
            "idx": 0,
        }
    ],
    "00495C01": [
        {
            "cmd": "battery_voltage_a",
            "format": "uint",
            "sensor": Sensor(
                "battery_voltage_a",
                Identifier.battery_voltage_a,
                unit="V",
                factor=100,
            ),
            "idx": 0,
        }
    ],
    "40495D01": [
        {
            "cmd": "battery_current_a",
            "format": "int",
            "sensor": Sensor(
                "battery_current_a",
                Identifier.battery_current_a,
                unit="A",
                factor=1000,
            ),
            "idx": 0,
        }
    ],
    "00696E01": [
        {
            "cmd": "BatteryInfo_Capacity",
            "format": "uint",
            "sensor": Sensor(
                "BatteryInfo_Capacity", Identifier.battery_capacity_total, unit="%"
            ),
            "idx": 0,
        }
    ],
    "00496901": [
        {
            "cmd": "BatteryInfo_Charge",
            "format": "uint",
            "sensor": Sensor(
                "BatteryInfo_Charge", Identifier.battery_power_charge_total, unit="W"
            ),
            "idx": 0,
        }
    ],
    "00496A01": [
        {
            "cmd": "BatteryInfo_Charge",
            "format": "uint",
            "sensor": Sensor(
                "BatteryInfo_DisCharge",
                Identifier.battery_power_discharge_total,
                unit="W",
            ),
            "idx": 0,
        }
    ],
    "00462501": [
        {
            "cmd": "EM_1",
            "format": "uint",
            "sensor": Sensor(
                "EM1_1 Identifier.metering_total_absorbed",
                Identifier.metering_total_absorbed,
                unit="kWh",
                factor=1000,
            ),
            "idx": 0,
        }
    ],
    "40463601": [
        {
            "cmd": "EM_3",
            "format": "uint",
            "sensor": Sensor(
                "EM3 Identifier.metering_power_supplied",
                Identifier.metering_power_supplied,
                unit="W",
            ),
            "idx": 0,
        }
    ],
    "40463701": [
        {
            "cmd": "EM_3",
            "format": "uint",
            "sensor": Sensor(
                "EM3 Identifier.metering_power_absorbed",
                Identifier.metering_power_absorbed,
                unit="W",
            ),
            "idx": 0,
        }
    ],
    "00893701": [
        {
            "cmd": "BatteryInfo_4",
            "format": "uint",
            "sensor": Sensor(
                "EM3 BatteryInfo_4", "TEMP battery_capacity_rated", unit="Wh"
            ),
            "idx": 4,
        }
    ],
    "08412509": [
        {
            "cmd": "BackupRelayStatus",
            "format": "uint",
            "sensor": Sensor(
                "BackupRelayStatus", "TEMP_BackupRelayStatus", mapper=SMATagList
            ),
            "idx": 0xFF,
        }
    ],
    # "00469109": [{ # Meter_Grid_FeedIn
    #             "cmd": "EM_2",
    #             "format": "uint",
    #             "sensor": Sensor("EM_2", Identifier., unit="kWh", factor=1000),
    #             "idx": 0
    # }],
    # "00469209": [{ # Meter_Grid_FeedIn
    #             "cmd": "EM_2",
    #             "format": "uint",
    #             "sensor": Sensor("EM_2", Identifier.battery_discharge_total, unit="kWh", factor=1000),
    #             "idx": 0
    # }],
    "0046E809": [
        {
            "cmd": "EM_4",
            "format": "uint",
            "sensor": Sensor(
                "active_power_feed_l1",
                Identifier.metering_active_power_feed_l1,
                unit="W",
            ),
            "idx": 0,
        }
    ],
    "0046E909": [
        {
            "cmd": "EM_4",
            "format": "uint",
            "sensor": Sensor(
                "active_power_feed_l2",
                Identifier.metering_active_power_feed_l2,
                unit="W",
            ),
            "idx": 0,
        }
    ],
    "0046EA09": [
        {
            "cmd": "EM_4",
            "format": "uint",
            "sensor": Sensor(
                "active_power_feed_l3",
                Identifier.metering_active_power_feed_l3,
                unit="W",
            ),
            "idx": 0,
        }
    ],
    "0046EB09": [
        {
            "cmd": "EM_4",
            "format": "uint",
            "sensor": Sensor(
                "active_power_draw_l1",
                Identifier.metering_active_power_draw_l1,
                unit="W",
            ),
            "idx": 0,
        }
    ],
    "0046EC09": [
        {
            "cmd": "EM_4",
            "format": "uint",
            "sensor": Sensor(
                "active_power_draw_l2",
                Identifier.metering_active_power_draw_l2,
                unit="W",
            ),
            "idx": 0,
        }
    ],
    "0046ED09": [
        {
            "cmd": "EM_4",
            "format": "uint",
            "sensor": Sensor(
                "active_power_draw_l3",
                Identifier.metering_active_power_draw_l3,
                unit="W",
            ),
            "idx": 0,
        }
    ],
    "40574609": [
        {
            "cmd": "SpotACCurrentBackup",
            "format": "uint",
            # "sensor": ,
            "idx": 0,
        }
    ],
    "40574709": [
        {
            "cmd": "SpotACCurrentBackup",
            "format": "uint",
            # "sensor": ,
            "idx": 0,
        }
    ],
    "40574809": [
        {
            "cmd": "SpotACCurrentBackup",
            "format": "uint",
            # "sensor": ,
            "idx": 0,
        }
    ],
    # "": [{
    #             "cmd": "",
    #             "format": "uint",
    #             "sensor": ,
    #             "idx": 0
    # }],
    # "": [{
    #             "cmd": "",
    #             "format": "uint",
    #             "sensor": ,
    #             "idx": 0
    # }],
    # "": [{
    #             "cmd": "",
    #             "format": "uint",
    #             "sensor": ,
    #             "idx": 0
    # }],
    # "": [{
    #             "cmd": "",
    #             "format": "uint",
    #             "sensor": ,
    #             "idx": 0
    # }],
    # "": [{
    #             "cmd": "",
    #             "format": "uint",
    #             "sensor": ,
    #             "idx": 0
    # }],
    # "": [{
    #             "cmd": "",
    #             "format": "uint",
    #             "sensor": ,
    #             "idx": 0
    # }],
}

commands: Dict[str, Dict[str, Any]] = {
    "login": {
        "command": 0xFFFD040C,
        "response": 0xFFFD040D,
        "first": 0x0030CB00,
        "last": 0x0030CB00,
    },
    "logoff": {"command": 0xFFFD010E, "response": 0xFFFD010F},
    "TypeLabel": {
        "command": 0x58000200,
        "first": 0x00821E00,
        "last": 0x008220FF,
    },
    "EnergyProduction": {
        "command": 0x54000200,
        "first": 0x00260100,
        "last": 0x002622FF,
    },
    "PVEnergyProduction": {
        "command": 0x54000200,
        "first": 0x0046C300,
        "last": 0x0046C3FF,
    },
    "SpotDCPower": {
        "command": 0x53800200,
        "first": 0x00251E00,
        "last": 0x00251EFF,
    },
    "SpotDCPower_3": {
        "command": 0x51000200,
        "first": 0x0046C200,
        "last": 0x0046C2FF,
    },
    "SpotACTotalPower": {
        "command": 0x51000200,
        "first": 0x00263F00,
        "last": 0x00263FFF,
    },
    "ChargeStatus": {
        "command": 0x51000200,
        "first": 0x00295A00,
        "last": 0x00295AFF,
    },
    "SpotDCVoltage": {
        "command": 0x53800200,
        "first": 0x00451F00,
        "last": 0x004521FF,
    },
    "SpotACCurrentBackup": {
        "command": 0x51000200,
        "first": 0x40574600,
        "last": 0x405748FF,
    },
    "BatteryInfo_TEMP": {
        "command": 0x51000200,
        "first": 0x00495B00,
        "last": 0x00495B10,
    },
    "BatteryInfo_UDC": {
        "command": 0x51000200,
        "first": 0x00495C00,
        "last": 0x00495C10,
    },
    "BatteryInfo_IDC": {
        "command": 0x51000200,
        "first": 0x00495D00,
        "last": 0x00495D10,
    },
    "BatteryInfo_Charge": {
        "command": 0x51000200,
        "first": 0x00496900,
        "last": 0x00496AFF,
    },
    "BatteryInfo_Capacity": {
        "command": 0x51000200,
        "first": 0x00696E00,
        "last": 0x00696E10,
    },
    "BatteryInfo": {
        "command": 0x51000200,
        "first": 0x00491E00,
        "last": 0x00495DFF,
    },
    "BatteryInfo_3": {
        "command": 0x58020200,
        "first": 0x08822C00,
        "last": 0x08822CFF,
    },
    "BatteryInfo_4": {
        "command": 0x58000200,
        "first": 0x00893700,
        "last": 0x008937FF,
    },
    "BatteryInfo_5": {
        "command": 0x58020200,
        "first": 0x00B18900,
        "last": 0x00B189FF,
    },
    "SpotGridFrequency": {
        "command": 0x51000200,
        "first": 0x00465700,
        "last": 0x004657FF,
    },
    "OperationTime": {
        "command": 0x54000200,
        "first": 0x00462E00,
        "last": 0x00462FFF,
    },
    "InverterTemperature": {
        "command": 0x52000200,
        "first": 0x00237700,
        "last": 0x002377FF,
        "format": "int",
    },
    "MaxACPower": {
        "command": 0x51000200,
        "first": 0x00411E00,
        "last": 0x004120FF,
    },
    "MaxACPower2": {
        "command": 0x51000200,
        "first": 0x00832A00,
        "last": 0x00832AFF,
    },
    "GridRelayStatus": {
        "command": 0x51800200,
        "first": 0x00416400,
        "last": 0x004164FF,
    },
    "BackupRelayStatus": {
        "command": 0x51800200,
        "first": 0x08412500,
        "last": 0x084125FF,
    },
    "GridConection": {
        "command": 0x51800200,
        "first": 0x0046A600,
        "last": 0x0046A6FF,
    },
    "OperatingStatus": {
        "command": 0x51800200,
        "first": 0x08412B00,
        "last": 0x08412BFF,
    },
    "GeneralOperatingStatus": {
        "command": 0x51800200,
        "first": 0x00412800,
        "last": 0x004128FF,
    },
    "WaitingTimeUntilFeedIn": {
        "command": 0x51000200,
        "first": 0x00416600,
        "last": 0x004166FF,
    },
    "DeviceStatus": {
        "command": 0x51800200,
        "first": 0x00214800,
        "last": 0x002148FF,
    },
    "SpotBatteryLoad": {
        "command": 0x54000200,
        "first": 0x00496700,
        "last": 0x004967FF,
    },
    "SpotBatteryUnload": {
        "command": 0x54000200,
        "first": 0x00496800,
        "last": 0x004968FF,
    },
    "EM_1": {
        "command": 0x54000200,
        "first": 0x00462400,
        "last": 0x004628FF,
    },
    "EM_2": {
        "command": 0x54000200,
        "first": 0x40469100,
        "last": 0x404692FF,
    },
    "EM_3": {
        "command": 0x51000200,
        "first": 0x00463600,
        "last": 0x004637FF,
    },
    "EM_4": {
        "command": 0x51000200,
        "first": 0x0046E800,
        "last": 0x0046EDFF,
    },
    "Insulation_1": {
        "command": 0x51020200,
        "first": 0x00254E00,
        "last": 0x00254FFF,
    },
    "Insulation_2": {
        "command": 0x51020200,
        "first": 0x00254F00,
        "last": 0x00254FFF,
    },
    "Firmware": {
        "command": 0x58000200,
        "first": 0x00823400,
        "last": 0x008234FF,
    },
    "energy_production": {
        "command": 0x54000200,
        "first": 0x00260100,
        "last": 0x002622FF,
    },
    "spot_ac_power": {
        "command": 0x51000200,
        "first": 0x00464000,
        "last": 0x004642FF,
    },
    "spot_ac_voltage": {
        "command": 0x51000200,
        "first": 0x00464800,
        "last": 0x004655FF,
    },
}


@dcs.dataclass(dcs.BIG_ENDIAN)
class speedwireHeader:
    """Speedwire header"""

    sma: Annotated[bytes, 4]
    tag42_length: dcs.U16
    tag42_tag0x02A0: dcs.U16
    group1: dcs.U32
    smanet2_length: dcs.U16
    smanet2_tagID: dcs.U16
    protokoll: dcs.U16

    def check6065(self) -> bool:
        """Check for 6065 Type, used by inverters. Size is not checked at this stage."""
        return (
            self.sma == b"SMA\x00"
            and self.tag42_length == 4
            and self.tag42_tag0x02A0 == 0x02A0
            and self.group1 == 1
            and self.smanet2_tagID == 0x10
            and self.protokoll == 0x6065
        )

    def check6069(self) -> bool:
        """Check for 6069 Type, used by energymeters.  Size is not checked at this stage."""
        return (
            self.sma == b"SMA\x00"
            and self.tag42_length == 4
            and self.tag42_tag0x02A0 == 0x02A0
            and self.group1 == 1
            and self.smanet2_tagID == 0x10
            and self.protokoll == 0x6069
        )

    def __str__(self) -> str:
        """customized output. Use hex-format for important values."""
        return f"speedwireHeader(sma:{self.sma!r} tag42_length:{self.tag42_length} tag42_tag0x02A0:{self.tag42_tag0x02A0:#04x} group1:{self.group1} smanet2_length:{self.smanet2_length} smanet2_tagID:{self.smanet2_tagID:#02x} protokoll:{self.protokoll:#04x})"

    def isDiscoveryResponse(self) -> bool:
        """Check if this message is a response to a discovery request."""
        return (
            self.sma == b"SMA\x00"
            and self.tag42_length == 4
            and self.tag42_tag0x02A0 == 0x02A0
            and self.group1 == 1
            and self.smanet2_length == 2
            and self.smanet2_tagID == 0
            and self.protokoll == 1
        )


@dcs.dataclass(dcs.BIG_ENDIAN)
class speedwireData2Tag:
    smanet2_lengthPayload: dcs.U16
    smanet2_id: dcs.U16
    protokoll: dcs.U16


@dcs.dataclass(dcs.LITTLE_ENDIAN)
class speedwireHeader6065:
    """Speedwire Header2 for 6065 Messages."""

    # https://github.com/RalfOGit/libspeedwire

    #        13 Bytes     0x26/38       00106065 09A0
    # $cmd = $cmdheader . $pktlength . $esignature . $target_ID . "0000" . $myID . "0000" . "00000000" . $spkt_ID . $cmd_ID . "00000000";

    unknown09A0E0: Annotated[bytes, 2]
    dest_susyid: dcs.U16
    dest_serial: dcs.U32
    dest_control: dcs.U16
    src_susyid: dcs.U16
    src_serial: dcs.U32
    src_control: dcs.U16
    error: dcs.U16
    fragment: dcs.U16

    pktId: dcs.U16
    cmdid: dcs.U32
    firstRegister: dcs.U32
    lastRegister: dcs.U32

    def isLoginResponse(self) -> bool:
        """Check if this message is a response to a login request."""
        return self.cmdid == 0xFFFD040D

    def __str__(self) -> str:
        """customized output. Use hex-format for important values."""
        return f"speedwireHeader6065(?:{self.unknown09A0E0.hex()} Src (ID,SNR,CNT): {self.src_susyid} {self.src_serial} {self.src_control} Dest (ID,SNR,CNT): {self.dest_susyid} {self.dest_serial} {self.dest_control}   error:{self.error} fragment:{self.fragment} pktId:{self.pktId} cmdid:{self.cmdid:#010x} firstRegister:{self.firstRegister:#010x} lastRegister:{self.lastRegister:#010x})"


@dcs.dataclass(dcs.BIG_ENDIAN)
class speedwireHeader6069:
    """Speedwire Header2 for 6069 Messages. 10 Bytes"""

    src_susyid: dcs.U16
    src_serial: dcs.U32

    timestamp: dcs.U32  # the 4 least significant bytes from a Unix Timestamp (msec since 1970) => int(time.time * 1000) & 0xFFFFFFFF)


@dcs.dataclass(dcs.LITTLE_ENDIAN)
class speedwireHeader6065x010:
    pass


# Originally based on https://github.com/Wired-Square/sma-query/blob/main/src/sma_query_sw/commands.py
class SpeedwireFrame:
    """Class for the send speedwire messages"""

    APP_ID = 125
    ANY_SERIAL = 0xFFFFFFFF
    ANY_SUSYID = 0xFFFF

    # Login Timeout in seconds
    LOGIN_TIMEOUT = 900

    def get_encoded_pw(self, password: str, installer: bool = False) -> bytearray:
        """Encodes the password"""
        byte_password = bytearray(password.encode("ascii"))

        if installer:
            login_code = 0xBB
        else:
            login_code = 0x88

        encodedpw = bytearray(12)

        for index in range(0, 12):
            if index < len(byte_password):
                encodedpw[index] = (login_code + byte_password[index]) % 256
            else:
                encodedpw[index] = login_code

        return encodedpw

    _frame_sequence = 1
    _id = (ctypes.c_ubyte * 4).from_buffer(bytearray(b"SMA\x00"))
    _tag0 = (ctypes.c_ubyte * 4).from_buffer(bytearray(b"\x00\x04\x02\xA0"))
    _group1 = (ctypes.c_ubyte * 4).from_buffer(bytearray(b"\x00\x00\x00\x01"))
    _eth_sig = (ctypes.c_ubyte * 4).from_buffer(bytearray(b"\x00\x10\x60\x65"))
    _ctrl2_1 = (ctypes.c_ubyte * 2).from_buffer(bytearray(b"\x00\x01"))
    _ctrl2_2 = (ctypes.c_ubyte * 2).from_buffer(bytearray(b"\x00\x01"))

    _data_length = 0  # Placeholder value
    _longwords = 0  # Placeholder value
    _ctrl = 0  # Placeholder value

    class FrameHeader(LittleEndianStructure):
        """Frame Header"""

        _pack_ = 1
        _fields_ = [
            ("id", ctypes.c_ubyte * 4),
            ("tag0", ctypes.c_ubyte * 4),
            ("group1", ctypes.c_ubyte * 4),
            ("data_length", ctypes.c_uint16),
            ("eth_sig", ctypes.c_ubyte * 4),
            ("longwords", ctypes.c_ubyte),
            ("ctrl", ctypes.c_ubyte),
        ]

    class DataHeader(LittleEndianStructure):
        # pylint: disable=too-few-public-methods
        """Data header"""
        _pack_ = 1
        _fields_ = [
            ("dst_sysyid", ctypes.c_uint16),
            ("dst_serial", ctypes.c_uint32),
            ("ctrl2_1", ctypes.c_ubyte * 2),
            ("app_id", ctypes.c_uint16),
            ("app_serial", ctypes.c_uint32),
            ("ctrl2_2", ctypes.c_ubyte * 2),
            ("preamble", ctypes.c_uint32),
            ("sequence", ctypes.c_uint16),
        ]

    class LogoutFrame(LittleEndianStructure):
        # pylint: disable=too-few-public-methods
        """Logout"""
        _pack_ = 1
        _fields_ = [
            ("command", ctypes.c_uint32),
            ("data_start", ctypes.c_uint32),
            ("data_end", ctypes.c_uint32),
        ]

    class LoginFrame(LittleEndianStructure):
        # pylint: disable=too-few-public-methods
        """Login"""
        _pack_ = 1
        _fields_ = [
            ("command", ctypes.c_uint32),
            ("login_type", ctypes.c_uint32),
            ("timeout", ctypes.c_uint32),
            ("time", ctypes.c_uint32),
            ("data_start", ctypes.c_uint32),
            ("user_password", ctypes.c_ubyte * 12),
            ("data_end", ctypes.c_uint32),
        ]

    class QueryFrame(LittleEndianStructure):
        # pylint: disable=too-few-public-methods
        """Query Frame"""

        _pack_ = 1
        _fields_ = [
            ("command", ctypes.c_uint32),
            ("first", ctypes.c_uint32),
            ("last", ctypes.c_uint32),
            ("data_end", ctypes.c_uint32),
        ]

    # def getLogoutFrame(self, inverter):
    #     frame_header = self.getFrameHeader()
    #     frame_data_header = self.getDataHeader(inverter)
    #     frame_data = self.LogoutFrame()

    #     frame_header.ctrl = 0xA0
    #     frame_data_header.dst_sysyid = 0xFFFF
    #     frame_data_header.ctrl2_1 = (ctypes.c_ubyte * 2).from_buffer(bytearray(b"\x00\x03"))
    #     frame_data_header.ctrl2_2 = (ctypes.c_ubyte * 2).from_buffer(bytearray(b"\x00\x03"))

    #     frame_data.command = commands["logoff"]["command"]
    #     frame_data.data_start = 0xFFFFFFFF
    #     frame_data.data_end = 0x00000000

    #     data_length = ctypes.sizeof(frame_data_header) + ctypes.sizeof(frame_data)

    #     frame_header.data_length = int.from_bytes(data_length.to_bytes(2, "big"), "little")

    #     frame_header.longwords = (data_length // 4)

    #     return bytes(frame_header) + bytes(frame_data_header) + bytes(frame_data)

    def getLoginFrame(self, password: str, serial: int, installer: bool) -> bytes:
        # pylint: disable=too-few-public-methods
        """Returns a Login Frame"""
        frame_header = self.getFrameHeader()
        frame_data_header = self.getDataHeader(password, serial)
        frame_data = self.LoginFrame()

        frame_header.ctrl = 0xA0
        frame_data_header.dst_sysyid = 0xFFFF
        frame_data_header.ctrl2_1 = (ctypes.c_ubyte * 2).from_buffer(
            bytearray(b"\x00\x01")
        )
        frame_data_header.ctrl2_2 = (ctypes.c_ubyte * 2).from_buffer(
            bytearray(b"\x00\x01")
        )

        frame_data.command = commands["login"]["command"]
        frame_data.login_type = (0x07, 0x0A)[installer]
        frame_data.timeout = self.LOGIN_TIMEOUT
        frame_data.time = int(time.time())
        frame_data.data_start = 0x00000000  # Data Start
        frame_data.user_password = (ctypes.c_ubyte * 12).from_buffer(
            self.get_encoded_pw(password, installer)
        )
        frame_data.date_end = 0x00000000  # Packet End

        data_length = ctypes.sizeof(frame_data_header) + ctypes.sizeof(frame_data)

        frame_header.data_length = int.from_bytes(
            data_length.to_bytes(2, "big"), "little"
        )

        frame_header.longwords = data_length // 4

        return bytes(frame_header) + bytes(frame_data_header) + bytes(frame_data)

    def getQueryFrame(self, password: str, serial: int, command_name: str) -> bytes:
        """Return Query Frame"""
        frame_header = self.getFrameHeader()
        frame_data_header = self.getDataHeader(password, serial)
        frame_data = self.QueryFrame()

        command = commands[command_name]

        frame_header.ctrl = 0xA0
        frame_data_header.dst_sysyid = 0xFFFF
        frame_data_header.ctrl2_1 = (ctypes.c_ubyte * 2).from_buffer(
            bytearray(b"\x00\x00")
        )
        frame_data_header.ctrl2_2 = (ctypes.c_ubyte * 2).from_buffer(
            bytearray(b"\x00\x00")
        )

        frame_data.command = command["command"]
        frame_data.first = command["first"]
        frame_data.last = command["last"]
        frame_data.date_end = 0x00000000

        data_length = ctypes.sizeof(frame_data_header) + ctypes.sizeof(frame_data)

        frame_header.data_length = int.from_bytes(
            data_length.to_bytes(2, "big"), "little"
        )

        frame_header.longwords = data_length // 4

        return bytes(frame_header) + bytes(frame_data_header) + bytes(frame_data)

    def getFrameHeader(self) -> FrameHeader:
        """Return Frame Header"""
        newFrameHeader = self.FrameHeader()
        newFrameHeader.id = self._id
        newFrameHeader.tag0 = self._tag0
        newFrameHeader.group1 = self._group1
        newFrameHeader.data_length = self._data_length
        newFrameHeader.eth_sig = self._eth_sig
        newFrameHeader.longwords = self._longwords
        newFrameHeader.ctrl = self._ctrl

        return newFrameHeader

    def getDataHeader(self, password: str, serial: int) -> DataHeader:
        """Return Data Header"""
        newDataHeader = self.DataHeader()

        newDataHeader.dst_susyid = self.ANY_SUSYID
        newDataHeader.dst_serial = self.ANY_SERIAL
        newDataHeader.ctrl2_1 = self._ctrl2_1
        newDataHeader.app_id = self.APP_ID
        newDataHeader.app_serial = serial
        newDataHeader.ctrl2_2 = self._ctrl2_2
        newDataHeader.preamble = 0
        newDataHeader.sequence = self._frame_sequence | 0x8000

        self._frame_sequence += 1

        return newDataHeader
