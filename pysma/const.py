"""
All Consts

"""

from typing import Dict


class Identifier:
    # pylint: disable=too-few-public-methods
    """All Sensor names
    This list is considered part of the pysam interface and
    changes to names are considered a breaking change
    """
    pv_power_a: str = "pv_power_a"
    pv_power_b: str = "pv_power_b"
    pv_power_c: str = "pv_power_c"
    pv_total_power_a: str = "pv_total_power_a"
    pv_total_power_b: str = "pv_total_power_b"
    pv_total_power_c: str = "pv_total_power_c"
    pv_voltage_a: str = "pv_voltage_a"
    pv_voltage_b: str = "pv_voltage_b"
    pv_voltage_c: str = "pv_voltage_c"
    pv_current_a: str = "pv_current_a"
    pv_current_b: str = "pv_current_b"
    pv_current_c: str = "pv_current_c"
    insulation_residual_current: str = "insulation_residual_current"
    pv_power: str = "pv_power"
    grid_power: str = "grid_power"
    frequency: str = "frequency"
    power_l1: str = "power_l1"
    power_l2: str = "power_l2"
    power_l3: str = "power_l3"
    temp_a: str = "temp_a"
    temp_b: str = "temp_b"
    temp_c: str = "temp_c"
    grid_reactive_power: str = "grid_reactive_power"
    grid_reactive_power_l1: str = "grid_reactive_power_l1"
    grid_reactive_power_l2: str = "grid_reactive_power_l2"
    grid_reactive_power_l3: str = "grid_reactive_power_l3"
    grid_apparent_power: str = "grid_apparent_power"
    grid_apparent_power_l1: str = "grid_apparent_power_l1"
    grid_apparent_power_l2: str = "grid_apparent_power_l2"
    grid_apparent_power_l3: str = "grid_apparent_power_l3"
    grid_power_factor: str = "grid_power_factor"
    current_l1: str = "current_l1"
    current_l2: str = "current_l2"
    current_l3: str = "current_l3"
    current_total: str = "current_total"
    voltage_l1: str = "voltage_l1"
    voltage_l2: str = "voltage_l2"
    voltage_l3: str = "voltage_l3"
    total_yield: str = "total_yield"
    daily_yield: str = "daily_yield"
    metering_power_supplied: str = "metering_power_supplied"
    metering_power_absorbed: str = "metering_power_absorbed"
    metering_frequency: str = "metering_frequency"
    metering_total_yield: str = "metering_total_yield"
    metering_total_absorbed: str = "metering_total_absorbed"
    metering_current_l1: str = "metering_current_l1"
    metering_current_l2: str = "metering_current_l2"
    metering_current_l3: str = "metering_current_l3"
    metering_voltage_l1: str = "metering_voltage_l1"
    metering_voltage_l2: str = "metering_voltage_l2"
    metering_voltage_l3: str = "metering_voltage_l3"
    metering_active_power_feed_l1: str = "metering_active_power_feed_l1"
    metering_active_power_feed_l2: str = "metering_active_power_feed_l2"
    metering_active_power_feed_l3: str = "metering_active_power_feed_l3"
    metering_active_power_draw_l1: str = "metering_active_power_draw_l1"
    metering_active_power_draw_l2: str = "metering_active_power_draw_l2"
    metering_active_power_draw_l3: str = "metering_active_power_draw_l3"
    metering_current_consumption: str = "metering_current_consumption"
    pv_gen_meter: str = "pv_gen_meter"
    sps_voltage: str = "sps_voltage"
    sps_current: str = "sps_current"
    sps_power: str = "sps_power"
    optimizer_serial: str = "optimizer_serial"
    optimizer_power: str = "optimizer_power"
    optimizer_current: str = "optimizer_current"
    optimizer_voltage: str = "optimizer_voltage"
    optimizer_temp: str = "optimizer_temp"
    battery_soc_total: str = "battery_soc_total"
    battery_soc_a: str = "battery_soc_a"
    battery_soc_b: str = "battery_soc_b"
    battery_soc_c: str = "battery_soc_c"
    battery_voltage_a: str = "battery_voltage_a"
    battery_voltage_b: str = "battery_voltage_b"
    battery_voltage_c: str = "battery_voltage_c"
    battery_current_a: str = "battery_current_a"
    battery_current_b: str = "battery_current_b"
    battery_current_c: str = "battery_current_c"
    battery_temp_a: str = "battery_temp_a"
    battery_temp_b: str = "battery_temp_b"
    battery_temp_c: str = "battery_temp_c"
    battery_capacity_total: str = "battery_capacity_total"
    battery_capacity_a: str = "battery_capacity_a"
    battery_capacity_b: str = "battery_capacity_b"
    battery_capacity_c: str = "battery_capacity_c"
    battery_charging_voltage_a: str = "battery_charging_voltage_a"
    battery_charging_voltage_b: str = "battery_charging_voltage_b"
    battery_charging_voltage_c: str = "battery_charging_voltage_c"
    battery_power_charge_total: str = "battery_power_charge_total"
    battery_power_charge_a: str = "battery_power_charge_a"
    battery_power_charge_b: str = "battery_power_charge_b"
    battery_power_charge_c: str = "battery_power_charge_c"
    battery_charge_total: str = "battery_charge_total"
    battery_charge_a: str = "battery_charge_a"
    battery_charge_b: str = "battery_charge_b"
    battery_charge_c: str = "battery_charge_c"
    battery_power_discharge_total: str = "battery_power_discharge_total"
    battery_power_discharge_a: str = "battery_power_discharge_a"
    battery_power_discharge_b: str = "battery_power_discharge_b"
    battery_power_discharge_c: str = "battery_power_discharge_c"
    battery_discharge_total: str = "battery_discharge_total"
    battery_discharge_a: str = "battery_discharge_a"
    battery_discharge_b: str = "battery_discharge_b"
    battery_discharge_c: str = "battery_discharge_c"
    serial_number: str = "serial_number"
    device_name: str = "device_name"
    device_type: str = "device_type"
    device_class: str = "device_class"
    device_manufacturer: str = "device_manufacturer"
    device_sw_version: str = "device_sw_version"
    inverter_power_limit: str = "inverter_power_limit"
    energy_meter: str = "energy_meter"
    operating_status_genereal: str = "operating_status_general"
    operating_status: str = "operating_status"
    operating_mode: str = "operating_mode"
    inverter_condition: str = "inverter_condition"
    inverter_system_init: str = "inverter_system_init"
    grid_connection_status: str = "grid_connection_status"
    grid_relay_status: str = "grid_relay_status"
    pv_isolation_resistance: str = "pv_isolation_resistance"
    grid_power_factor_excitation: str = "grid_power_factor_excitation"
    metering_total_consumption: str = "metering_total_consumption"
    battery_status_operating_mode: str = "battery_status_operating_mode"
    status: str = "status"
    active_power_limitation: str = "active_power_limitation"
    power_limit_via_io: str = "power_limit_via_io"
    charging_station_total_absorbed: str = "charging_station_total_absorbed"
    charging_station_power_absorbed: str = "charging_station_power_absorbed"

    operating_mode_plant_control: str = "operating_mode_plant_control"
    power_setpoint_plant_control: str = "power_setpoint_plant_control"

    charging_mode: str = "charging_mode"  # channel="Parameter.Chrg.ActChaMod"
    charge_current_limit: str = (
        "charge_current_limit"  # channel="Parameter.Inverter.AcALim"
    )
    power_limit_in: str = "power_limit_in"  # channel="Parameter.Inverter.WMaxIn"
    active_power_limitation_gcp = "active_power_limitation_gcp"


# Data-Source:
# https://www.sma.de/produkte/solar-wechselrichter/sunny-tripower-x
# Technical Information - Parameters and Measured Values
# STP 12-50 / STP 15-50 / STP 20-50 / STP 25-50 (Sunny Tripower X)
# with firmware package 03.02.07.R
# https://github.com/sma-bluetooth/sma-bluetooth/blob/master/smatool.xml
SMATagList: Dict[int, str] = {
    35: "Error",
    51: "Closed",
    270: "Energy Meter",
    276: "Instantaneous value",
    295: "MPP",
    303: "Off",
    307: "OK",
    308: "On",
    309: "Operation",
    311: "Open",
    325: "Phase L1 (phsA)",
    326: "Phases L1, L2 and L3 (phsABC)",
    327: "Phase L2 (phsB)",
    329: "Phase L3 (phsC)",
    336: "Contact the manufacturer",
    337: "Contact the installer",
    338: "Invalid",
    349: "Energy Meter 2",
    372: "Sunny Home Manager 2",
    381: "Stop",
    402: "Phases L1 and L2 (phsAB)",
    403: "Phases L1 and L3 (phsAC)",
    404: "Phases L2 and L3 (phsBC)",
    443: "Constant voltage",
    455: "Warning",
    461: "SMA",
    569: "activated",
    802: "Active",
    803: "Inactive",
    887: "No recommended action",
    1041: "leading / overexcited",
    1042: "lagging / underexcited",
    1069: "Reactive power / voltage characteristic curve Q(V)",
    1070: "Reactive power Q, direct setpoint",
    1071: "Reactive power const. Q (kVAr)",
    1072: "Q specified by PV system control",
    1073: "Reactive power Q(P)",
    1074: "cos φ, direct setpoint",
    1075: "cos φ, setpoint via system control",
    1076: "cos φ(P) characteristic curve",
    1077: "Active power limitation P (W)",
    1078: "Active power limitation P (%) of PMAX",
    1079: "Active power limitation P via system control",
    1129: "Yes",
    1130: "No",
    1264: "Full dynamic grid support",
    1265: "Limited dynamic grid support",
    1295: "Standby",
    1387: "Reactive power Q, setpoint via analog input",
    1388: "cos φ, setpoint via analog input",
    1389: "Reactive power / voltage characteristic curve Q(U) with hysteresis and deadband",
    1390: "Active power limitation P via analog input",
    1391: "Active power limitation P via digital inputs",
    1392: "Errors",
    1393: "Wait for PV voltage",
    1394: "Wait for valid AC grid",
    1395: "DC area",
    1396: "AC grid",
    1438: "Automatic",
    1455: "Emergency stop",
    1463: "backup",
    1466: "Waiting",
    1467: "Starting",
    1468: "MPP search",
    1469: "Shutdown",
    1470: "Event message",
    1471: "Warning/error e-mail OK",
    1472: "Warning/error e-mail not OK",
    1473: "System info Parameter.Nameplate.Modele-mail OK",
    1474: "System info e-mail not OK",
    1475: "Error e-mail OK",
    1476: "Error e-mail not OK",
    1477: "Warning e-mail OK",
    1478: "Warning e-mail not OK",
    1479: "Wait after grid interruption",
    1480: "Wait for electric utility company",
    1749: "Full Stop",
    1779: "disconnected",
    1780: "public grid",
    1781: "off-Grid",
    1795: "locked",
    # 2055: "Status digital inlet: DI1",
    # 2056: "Status digital inlet: DI1, DI2",
    # 2057: "Status digital inlet: DI1, DI2, DI3",
    # 2058: "Status digital inlet: DI1, DI2, DI3, DI4",
    # 2059: "Status digital inlet: DI1, DI2, DI4",
    # 2060: "Status digital inlet: DI1, DI3",
    # 2061: "Status digital inlet: DI1, DI3, DI4",
    # 2062: "Status digital inlet: DI1, DI4",
    # 2063: "Status digital inlet: DI2",
    # 2064: "Status digital inlet: DI2, DI3",
    # 2065: "Status digital inlet: DI2, DI3, DI4",
    # 2066: "Status digital inlet: DI2, DI4",
    # 2067: "Status digital inlet: DI3",
    # 2068: "Status digital inlet: DI3, DI4",
    # 2069: "Status digital inlet: DI4",
    2119: "derating",
    2270: "cos φ or Q specification through optimum PV system control",
    2506: "Values maintained",
    2507: "Apply fallback values",
    4354: "Maximum active power export",
    4405: "Maximum active power WMax",
    4406: "Maximum reactive power VArMax",
    4433: "Zero at dead band boundary",
    4434: "Zero at origin (ZerAtZer)",
    4443: "Current power",
    4444: "Potential power",
    4450: "Q limitation",
    4562: "cos φ(V) charac. curve",
    4520: "Mean value of the phase voltages",
    4521: "Maximum phase voltage",
    4718: "Boost Charging",  # EV-Charger
    4950: "Smart Chargig",  # EV-Charger
    5169: "Station locked",  # EV-Charger
    5249: "Potential power with characteristic curve break",
    # Device Classes
    8000: "All Devices",
    8001: "Solar Inverters",
    8002: "Wind Turbine Inverter",
    8007: "Batterie Inverters",
    8008: "EV Chargers",
    8009: "Hybrid Inverters",
    # Inverter Classes
    9000: "SWR 700",
    9001: "SWR 850",
    9002: "SWR 850E",
    9003: "SWR 1100",
    9004: "SWR 1100E",
    9005: "SWR 1100LV",
    9006: "SWR 1500",
    9007: "SWR 1600",
    9008: "SWR 1700E",
    9009: "SWR 1800U",
    9010: "SWR 2000",
    9011: "SWR 2400",
    9012: "SWR 2500",
    9013: "SWR 2500U",
    9014: "SWR 3000",
    9015: "SB 700",
    9016: "SB 700U",
    9017: "SB 1100",
    9018: "SB 1100U",
    9019: "SB 1100LV",
    9020: "SB 1700",
    9021: "SB 1900TLJ",
    9022: "SB 2100TL",
    9023: "SB 2500",
    9024: "SB 2800",
    9025: "SB 2800i",
    9026: "SB 3000",
    9027: "SB 3000US",
    9028: "SB 3300",
    9029: "SB 3300U",
    9030: "SB 3300TL",
    9031: "SB 3300TL HC",
    9032: "SB 3800",
    9033: "SB 3800U",
    9034: "SB 4000US",
    9035: "SB 4200TL",
    9036: "SB 4200TL HC",
    9037: "SB 5000TL",
    9038: "SB 5000TLW",
    9039: "SB 5000TL HC",
    9040: "Convert 2700",
    9041: "SMC 4600A",
    9042: "SMC 5000",
    9043: "SMC 5000A",
    9044: "SB 5000US",
    9045: "SMC 6000",
    9046: "SMC 6000A",
    9047: "SB 6000US",
    9048: "SMC 6000UL",
    9049: "SMC 6000TL",
    9050: "SMC 6500A",
    9051: "SMC 7000A",
    9052: "SMC 7000HV",
    9053: "SB 7000US",
    9054: "SMC 7000TL",
    9055: "SMC 8000TL",
    9056: "SMC 9000TL-10",
    9057: "SMC 10000TL-10",
    9058: "SMC 11000TL-10",
    9059: "SB 3000 K",
    9060: "Unknown device",
    9061: "SensorBox",
    9062: "SMC 11000TLRP",
    9063: "SMC 10000TLRP",
    9064: "SMC 9000TLRP",
    9065: "SMC 7000HVRP",
    9066: "SB 1200",
    9067: "STP 10000TL-10",
    9068: "STP 12000TL-10",
    9069: "STP 15000TL-10",
    9070: "STP 17000TL-10",
    9071: "SB 2000HF-30",
    9072: "SB 2500HF-30",
    9073: "SB 3000HF-30",
    9074: "SB 3000TL-21",
    9075: "SB 4000TL-21",
    9076: "SB 5000TL-21",
    9077: "SB 2000HFUS-30",
    9078: "SB 2500HFUS-30",
    9079: "SB 3000HFUS-30",
    9080: "SB 8000TLUS",
    9081: "SB 9000TLUS",
    9082: "SB 10000TLUS",
    9083: "SB 8000US",
    9084: "WB 3600TL-20",
    9085: "WB 5000TL-20",
    9086: "SB 3800US-10",
    9087: "Sunny Beam BT11",
    9088: "Sunny Central 500CP",
    9089: "Sunny Central 630CP",
    9090: "Sunny Central 800CP",
    9091: "Sunny Central 250U",
    9092: "Sunny Central 500U",
    9093: "Sunny Central 500HEUS",
    9094: "Sunny Central 760CP",
    9095: "Sunny Central 720CP",
    9096: "Sunny Central 910CP",
    9097: "SMU8",
    9098: "STP 5000TL-20",
    9099: "STP 6000TL-20",
    9100: "STP 7000TL-20",
    9101: "STP 8000TL-10",
    9102: "STP 9000TL-20",
    9103: "STP 8000TL-20",
    9104: "SB 3000TL-JP-21",
    9105: "SB 3500TL-JP-21",
    9106: "SB 4000TL-JP-21",
    9107: "SB 4500TL-JP-21",
    9108: "SCSMC",
    9109: "SB 1600TL-10",
    9110: "SSM US",
    9111: "SMA radio-controlled socket",
    9112: "WB 2000HF-30",
    9113: "WB 2500HF-30",
    9114: "WB 3000HF-30",
    9115: "WB 2000HFUS-30",
    9116: "WB 2500HFUS-30",
    9117: "WB 3000HFUS-30",
    9118: "VIEW-10",
    9119: "Sunny Home Manager",
    9120: "SMID",
    9121: "Sunny Central 800HE-20",
    9122: "Sunny Central 630HE-20",
    9123: "Sunny Central 500HE-20",
    9124: "Sunny Central 720HE-20",
    9125: "Sunny Central 760HE-20",
    9126: "SMC 6000A-11",
    9127: "SMC 5000A-11",
    9128: "SMC 4600A-11",
    9129: "SB 3800-11",
    9130: "SB 3300-11",
    9131: "STP 20000TL-10",
    9132: "SMA CT Meter",
    9133: "SB 2000HFUS-32",
    9134: "SB 2500HFUS-32",
    9135: "SB 3000HFUS-32",
    9136: "WB 2000HFUS-32",
    9137: "WB 2500HFUS-32",
    9138: "WB 3000HFUS-32",
    9139: "STP 20000TLHE-10",
    9140: "STP 15000TLHE-10",
    9141: "SB 3000US-12",
    9142: "SB 3800US-12",
    9143: "SB 4000US-12",
    9144: "SB 5000US-12",
    9145: "SB 6000US-12",
    9146: "SB 7000US-12",
    9147: "SB 8000US-12",
    9148: "SB 8000TLUS-12",
    9149: "SB 9000TLUS-12",
    9150: "SB 10000TLUS-12",
    9151: "SB 11000TLUS-12",
    9152: "SB 7000TLUS-12",
    9153: "SB 6000TLUS-12",
    9154: "SB 1300TL-10",
    9155: "Sunny Backup 2200",
    9156: "Sunny Backup 5000",
    9157: "Sunny Island 2012",
    9158: "Sunny Island 2224",
    9159: "Sunny Island 5048",
    9160: "SB 3600TL-20",
    9161: "SB 3000TL-JP-22",
    9162: "SB 3500TL-JP-22",
    9163: "SB 4000TL-JP-22",
    9164: "SB 4500TL-JP-22",
    9165: "SB 3600TL-21",
    9167: "Cluster Controller",
    9168: "SC630HE-11",
    9169: "SC500HE-11",
    9170: "SC400HE-11",
    9171: "WB 3000TL-21",
    9172: "WB 3600TL-21",
    9173: "WB 4000TL-21",
    9174: "WB 5000TL-21",
    9175: "SC 250",
    9176: "SMA Meteo Station",
    9177: "SB 240-10",
    9178: "SB 240-US-10",
    9179: "Multigate-10",
    9180: "Multigate-US-10",
    9181: "STP 20000TLEE-10",
    9182: "STP 15000TLEE-10",
    9183: "SB 2000TLST-21",
    9184: "SB 2500TLST-21",
    9185: "SB 3000TLST-21",
    9186: "WB 2000TLST-21",
    9187: "WB 2500TLST-21",
    9188: "WB 3000TLST-21",
    9189: "WTP 5000TL-20",
    9190: "WTP 6000TL-20",
    9191: "WTP 7000TL-20",
    9192: "WTP 8000TL-20",
    9193: "WTP 9000TL-20",
    9194: "STP 12000TL-US-10",
    9195: "STP 15000TL-US-10",
    9196: "STP 20000TL-US-10",
    9197: "STP 24000TL-US-10",
    9198: "SB 3000TLUS-22",
    9199: "SB 3800TLUS-22",
    9200: "SB 4000TLUS-22",
    9201: "SB 5000TLUS-22",
    9202: "WB 3000TLUS-22",
    9203: "WB 3800TLUS-22",
    9204: "WB 4000TLUS-22",
    9205: "WB 5000TLUS-22",
    9206: "SC 500CP-JP",
    9207: "SC 850CP",
    9208: "SC 900CP",
    9209: "SC 850 CP-US",
    9210: "SC 900 CP-US",
    9211: "SC 619CP",
    9212: "SMA Meteo Station",
    9213: "SC 800 CP-US",
    9214: "SC 630 CP-US",
    9215: "SC 500 CP-US",
    9216: "SC 720 CP-US",
    9217: "SC 750 CP-US",
    9218: "SB 240 Dev",
    9219: "SB 240-US BTF",
    9220: "Grid Gate-20",
    9221: "SC 500 CP-US/600V",
    9222: "STP 10000TLEE-JP-10",
    9223: "Sunny Island 6.0H-11",
    9224: "Sunny Island 8.0H-11",
    9225: "SB 5000SE-10",
    9226: "SB 3600SE-10",
    9227: "SC 800CP-JP",
    9228: "SC 630CP-JP",
    9229: "WebBox-30",
    9230: "Power Reducer Box",
    9231: "Sunny Sensor Counter",
    9232: "Sunny Boy Control",
    9233: "Sunny Boy Control Plus",
    9234: "Sunny Boy Control Light",
    9235: "Sunny Central 100 Outdoor",
    9236: "Sunny Central 1000MV",
    9237: "Sunny Central 100 LV",
    9238: "Sunny Central 1120MV",
    9239: "Sunny Central 125 LV",
    9240: "Sunny Central 150",
    9241: "Sunny Central 200",
    9242: "Sunny Central 200 HE",
    9243: "Sunny Central 250 HE",
    9244: "Sunny Central 350",
    9245: "Sunny Central 350 HE",
    9246: "Sunny Central 400 HE",
    9247: "Sunny Central 400MV",
    9248: "Sunny Central 500 HE",
    9249: "Sunny Central 500MV",
    9250: "Sunny Central 560 HE",
    9251: "Sunny Central 630 HE",
    9252: "Sunny Central 700MV",
    9253: "Sunny Central Betriebsführung",
    9254: "Sunny Island 3324",
    9255: "Sunny Island 4.0M",
    9256: "Sunny Island 4248",
    9257: "Sunny Island 4248U",
    9258: "Sunny Island 4500",
    9259: "Sunny Island 4548U",
    9260: "Sunny Island 5.4M",
    9261: "Sunny Island 5048U",
    9262: "Sunny Island 6048U",
    9263: "Sunny Mini Central 7000HV-11",
    9264: "Sunny Solar Tracker",
    9265: "Sunny Beam",
    9266: "Sunny Boy SWR 700/150",
    9267: "Sunny Boy SWR 700/200",
    9268: "Sunny Boy SWR 700/250",
    9269: "Sunny WebBox for SC",
    9270: "Sunny WebBox",
    9271: "STP 20000TLEE-JP-11",
    9272: "STP 10000TLEE-JP-11",
    9273: "SB 6000TL-21",
    9274: "SB 6000TL-US-22",
    9275: "SB 7000TL-US-22",
    9276: "SB 7600TL-US-22",
    9277: "SB 8000TL-US-22",
    9278: "Sunny Island 3.0M-11",
    9279: "Sunny Island 4.4M-11",
    9281: "STP 10000TL-20",
    9282: "STP 11000TL-20",
    9283: "STP 12000TL-20",
    9284: "STP 20000TL-30",
    9285: "STP 25000TL-30",
    9286: "Sunny Central Storage 500",
    9287: "Sunny Central Storage 630",
    9288: "Sunny Central Storage 720",
    9289: "Sunny Central Storage 760",
    9290: "Sunny Central Storage 800",
    9291: "Sunny Central Storage 850",
    9292: "Sunny Central Storage 900",
    9293: "SB 7700TL-US-22",
    9294: "SB20.0-3SP-40",
    9295: "SB30.0-3SP-40",
    9301: "SB1.5-1VL-40",
    9302: "SB2.5-1VL-40",
    9303: "SB2.0-1VL-40",
    9304: "SB5.0-1SP-US-40",
    9305: "SB6.0-1SP-US-40",
    9306: "SB8.0-1SP-US-40",
    9310: "STP 30000TL-US-10",
    9311: "STP 25000TL-JP-30",
    9313: "SB50.0-3SP-40",
    9319: "SB3.0-1AV-40 (Sunny Boy 3.0 AV-40)",
    9320: "SB3.6-1AV-40 (Sunny Boy 3.6 AV-40)",
    9321: "SB4.0-1AV-40 (Sunny Boy 4.0 AV-40)",
    9322: "SB5.0-1AV-40 (Sunny Boy 5.0 AV-40)",
    9324: "SBS1.5-1VL-10 (Sunny Boy Storage 1.5)",
    9325: "SBS2.0-1VL-10 (Sunny Boy Storage 2.0)",
    9326: "SBS2.5-1VL-10 (Sunny Boy Storage 2.5)",
    9327: "SMA Energy Meter",
    9331: "SI 3.0M-12 (Sunny Island 3.0M)",
    9332: "SI 4.4M-12 (Sunny Island 4.4M)",
    9333: "SI 6.0H-12 (Sunny Island 6.0H)",
    9334: "SI 8.0H-12 (Sunny Island 8.0H)",
    9335: "SMA Com Gateway",
    9336: "STP 15000TL-30",
    9337: "STP 17000TL-30",
    9343: "Sunny Home Manager 2",
    9344: "STP4.0-3AV-40 (Sunny Tripower 4.0)",
    9345: "STP5.0-3AV-40 (Sunny Tripower 5.0)",
    9346: "STP6.0-3AV-40 (Sunny Tripower 6.0)",
    9347: "STP8.0-3AV-40 (Sunny Tripower 8.0)",
    9348: "STP10.0-3AV-40 (Sunny Tripower 10.0)",
    9356: "SBS3.7-1VL-10 (Sunny Boy Storage 3.7)",
    9358: "SBS5.0-10 (Sunny Boy Storage 5.0)",
    9359: "SBS6.0-10 (Sunny Boy Storage 6.0)",
    9366: "STP3.0-3AV-40 (Sunny Tripower 3.0)",
    9401: "SB3.0-1AV-41 (Sunny Boy 3.0 AV-41)",
    9402: "SB3.6-1AV-41 (Sunny Boy 3.6 AV-41)",
    9403: "SB4.0-1AV-41 (Sunny Boy 4.0 AV-41)",
    9404: "SB5.0-1AV-41 (Sunny Boy 5.0 AV-41)",
    9405: "SB6.0-1AV-41 (Sunny Boy 6.0 AV-41)",
    9354: "STP 24500TL-JP-30",
    9473: "SI 3.0M-13 (Sunny Island 3.0M)",
    9474: "SI 4.4M-13 (Sunny Island 4.4M)",
    9475: "SI 6.0H-13 (Sunny Island 6.0H)",
    9476: "SI 8.0H-13 (Sunny Island 8.0H)",
    9488: "SUNNY TRIPOWER X 25",
    9489: "SUNNY TRIPOWER X 20",
    9491: "SUNNY TRIPOWER X 15",
    9492: "SUNNY TRIPOWER X 12",
    9483: "EVC7.4-1AC-10",
    9484: "EVC22-3AC-10",
    19048: "STP5.0SE (SUNNY TRIPOWER 5.0 SE)",
    19049: "STP6.0SE (SUNNY TRIPOWER 6.0 SE)",
    19050: "STP8.0SE (SUNNY TRIPOWER 8.0 SE)",
    19051: "STP10.0SE (SUNNY TRIPOWER 10.0 SE)",
    19085: "Sunny Boy Smart Energy 6.0",
    19128: "Sunny Boy Smart Energy 3.6",
    19129: "Sunny Boy Smart Energy 4.0",
    19130: "Sunny Boy Smart Energy 5.0",
    19143: "EVC22-3AC-20",
    200111: "Not connected",  # EV-Charger
    200112: "Sleep Mode",  # EV-Charger
    200113: "Active Mode",  # EV-Charger
    16777213: "Information not available",
}
