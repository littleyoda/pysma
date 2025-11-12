"""Test pysma const file."""
import pysma.definitions_webconnect
from pysma.definitions_ennexos import ennexosSensorProfiles, name2sensor
from pysma.definitions_speedwire import commands
from pysma.sensor import Sensor


def test_duplicate_sensors_webconnect():
    """Test if defined sensors have unique key and name."""
    variables = vars(pysma.definitions_webconnect)
    found_keys = []
    found_names = []
    for value in variables.values():
        if isinstance(value, Sensor):
            found_key = f"{value.key}_{value.key_idx}"
            found_name = value.name

            assert found_key not in found_keys
            found_keys.append(found_key)

            assert found_name not in found_names
            found_names.append(found_name)


def test_sensor_map():
    """Test if all map entries only contain unique items."""
    for sensor_map in pysma.definitions_webconnect.sensor_map.values():
        unique_items = list({f"{s.key}_{s.key_idx}": s for s in sensor_map}.values())
        assert unique_items == sensor_map


def test_sameunit_for_all_sensors():
    errCount = 0
    webconnect_sensors = []
    for sensors in pysma.definitions_webconnect.sensor_map.values():
        for sensor in sensors:
            if not isinstance(sensor, Sensor):
                print(f"Not a Sesnsor Webconnect {type(sensor)}: {sensor}")
            else:
                webconnect_sensors.append(sensor)

    enneox_sensors = []
    for sensorsDef in ennexosSensorProfiles:
        print(sensorsDef[0])
        for sensorname in sensorsDef[1]:
            if sensorname not in name2sensor:
                print(f"Enneox-Sensor {sensorname} not found")
                continue
            enneox_sensors.append(name2sensor[sensorname])

    speedwire_sensors = []
    for c in commands.values():
        for r in c.get("registers", []):
            if "sensor" in r:
                sensor = r["sensor"]
                if not isinstance(sensor, Sensor):
                    print(f"Not a Sesnsor {type(sensor)}: {sensor}")
                    errCount += 1
                else:
                    speedwire_sensors.append(sensor)

    id2unit = {}
    for arr in [webconnect_sensors, enneox_sensors, speedwire_sensors]:
        for sen in arr:
            if sen.name in id2unit:
                if sen.unit != id2unit[sen.name]:
                    errCount += 1
                    print(
                        f"inconsistent units {sen.name} {sen.unit} <=>  {id2unit[sen.name]}"
                    )
            else:
                id2unit[sen.name] = sen.unit
    print(f"Tested {len(id2unit)}")
    assert errCount == 0
