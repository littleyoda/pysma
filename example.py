#!/usr/bin/env python
"""Basic usage example and testing of pysma."""
import argparse
import asyncio
import logging
import queue
import signal
import socket
import sys
import webbrowser
from typing import Any

import aiohttp

import pysmaplus as pysma
from pysmaplus.helpers import toJson
from pysmaplus.semp import device, semp
from pysmaplus.sensor import Sensors

# This example will work with Python 3.9+

_LOGGER = logging.getLogger(__name__)

VAR: dict[str, Any] = {}
log_queue: queue.Queue = queue.Queue()


class QueuingHandler(logging.Handler):
    def __init__(self, *args, message_queue, **kwargs):
        """Initialize by copying the queue and sending everything else to superclass."""
        logging.Handler.__init__(self, *args, **kwargs)
        self.message_queue = message_queue

    def emit(self, record):
        """Add the formatted log message (sans newlines) to the queue."""
        self.message_queue.put(self.format(record).rstrip("\n"))


def print_table(sensors: Sensors) -> None:
    """Print sensors formatted as table."""
    if len(sensors) == 0:
        print("No Sensors found!")
    for sen in sensors:
        if sen.value is None:
            print("{:>25}".format(sen.name))
        else:
            name = sen.name
            if sen.key:
                name = sen.key
            print(
                "{:>25}{:>15} {} {} {}".format(
                    name,
                    str(sen.value),
                    sen.unit if sen.unit else "",
                    sen.mapped_value if sen.mapped_value else "",
                    sen.range if sen.range else "",
                )
            )


async def discovery(savedebug: bool, doIdentification: bool) -> None:
    # Run Discovery Request
    debug: dict[str, Any] = {"cmd": "discovery", "addr": [], "id": {}}
    ret = await pysma.discovery()
    if len(ret) == 0:
        print("Found no SMA devices via speedwire discovery request!")
    for r in ret:
        print(f"{r[0]}:{r[1]}")
    debug["addr"] = ret

    # Check every host found
    if doIdentification and len(ret) > 0:
        print("\nTrying to identify... (can take up to 30 seconds pre device)\n")
        for r in ret:
            print(r[0])
            ident = await identify(r[0], False)
            debug["id"][r[0]] = ident
            print()

    if savedebug:
        f = open("example.log", "w")
        f.write(toJson(debug))


async def identify(url: str, savedebug: bool) -> list:
    order_list = ["found", "maybe", "failed"]
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    ) as session:
        ret = await pysma.autoDetect(session, url)
        ret_sorted = sorted(ret, key=lambda x: order_list.index(x.status))
        print("{:>15}{:>10}    {}".format("Access", "", "Remarks"))
        for r in ret_sorted:
            print(
                "{:>15}{:>10}    {}".format(
                    r.access, r.status, (r.remark + " " + r.device).strip()
                )
            )
        if savedebug:
            f = open("example.log", "w")
            f.write(toJson(ret))
        return ret


async def main_loop(args: argparse.Namespace) -> None:
    """Run main loop."""
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    ) as session:
        user = args.user
        password = args.password
        url = args.url
        accessmethod = args.accessmethod
        delay = args.delay
        cnt = args.count
        savedebug = args.save
        isVerbose = args.verbose
        ignoretimeouts = (args.ignoretimeouts,)
        options = (
            dict(map(lambda s: s.split("="), args.options)) if args.options else {}
        )
        setvalue = (  # noqa: F841
            dict(map(lambda s: s.split("="), args.set)) if args.set else {}
        )

        _LOGGER.debug(
            f"MainLoop called! Url: {url} User/Group: {user} Accessmethod: {accessmethod}"
        )
        VAR["sma"] = pysma.getDevice(session, url, password, user, accessmethod)
        assert VAR["sma"]
        VAR["sma"].set_options(options)
        try:
            await VAR["sma"].new_session()
        except pysma.exceptions.SmaAuthenticationException:
            _LOGGER.error("Authentication failed!")
            return
        except pysma.exceptions.SmaConnectionException:
            _LOGGER.error("Unable to connect to device at %s", url)
            return
        # We should not get any exceptions, but if we do we will close the session.
        try:
            VAR["running"] = True
            devicelist = await VAR["sma"].device_list()
            for deviceId, deviceData in devicelist.items():
                for name, value in deviceData.asDict().items():
                    if type(value) in [str, float, int]:
                        print("{:>17}{:>25}".format(name, value))
                print(
                    "====================================================================================="
                )

            sensors: dict[str, Sensors] = {}
            for deviceId in devicelist.keys():
                sensors[deviceId] = await VAR["sma"].get_sensors(deviceId)
                for sensor in sensors[deviceId]:
                    sensor.enabled = True

            # TODO
            # Set Parameters if requested
            # for pname, pvalue in setvalue.items():
            #     psensor = [
            #         sen for sen in sensors if sen.name == pname or sen.key == pname
            #     ]
            #     if len(psensor) != 1:
            #         raise ValueError("Sensor not found %s %s", pname, psensor)
            #     await VAR["sma"].set_parameter(psensor[0], int(pvalue))

            while VAR.get("running"):
                for deviceId in devicelist.keys():
                    print("Device-ID: " + str(deviceId))
                    try:
                        await VAR["sma"].read(sensors[deviceId], deviceId)
                        print_table(sensors[deviceId])
                    except TimeoutError as e:
                        if not ignoretimeouts:
                            raise e
                        print("Timeout")
                    print(
                        "---------------------------------------------------------------------------"
                    )
                cnt -= 1
                if cnt == 0:
                    break
                await asyncio.sleep(delay)
                print(
                    "====================================================================================="
                )
        finally:
            _LOGGER.info("Closing Session...")
            debug = await VAR["sma"].get_debug()
            debug["cmd"] = accessmethod
            debug["version"] = getVersion()
            if isVerbose:
                print(toJson(debug))
            if savedebug:
                debug["log"] = list(log_queue.queue)
                f = open("example.log", "w")
                f.write(toJson(debug))
            await VAR["sma"].close_session()


def getVersion() -> str:
    versionstring = "unknown"
    from importlib.metadata import PackageNotFoundError, version

    try:
        versionstring = version("pysma-plus")
    except PackageNotFoundError:
        pass
    return versionstring


def setupLogging(verbose: bool):

    #    LOG_FORMAT = '%(asctime)s: %(levelname)8s: %(name)20s:  %(message)s'
    LOG_FORMAT = "%(levelname)8s: %(name)30s:  %(message)s"

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    handler = QueuingHandler(message_queue=log_queue, level=logging.DEBUG)
    formatter = logging.Formatter(LOG_FORMAT)
    formatter.default_time_format = "%H:%M:%S"
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG if verbose else logging.ERROR)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


async def sempdemo():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    print(f"Using {ip_address}...")

    control = semp(ip_address, 8080)
    devId = "F-11223344-312233445501-00"
    dev = device(devId, "Testgerät", "Other", "1", "None", 1000)
    control.addDevice(dev)
    control.getDevice(devId).setPowerStatus(0, "off")

    await control.start()
    webbrowser.open(f"http://{ip_address}:8080")
    while True:
        await asyncio.sleep(5 * 60)
        print("Turning device on...")
        control.getDevice(devId).setPowerStatus(1000, "on")
        await asyncio.sleep(5 * 60)
        print("Turning device off...")
        control.getDevice(devId).setPowerStatus(0, "off")


async def main() -> None:
    print("Library version: " + getVersion())
    parser = argparse.ArgumentParser(
        prog="python example.py",
        description="Test the pysma library.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug output"
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=2,
        help="Delay between two requests [seconds]",
    )
    parser.add_argument(
        "-c", "--count", type=int, default=1, help="Number of requests (0=unlimited)"
    )
    parser.add_argument(
        "-s",
        "--save",
        action="store_true",
        help="Save debug information to example.log",
    )
    parser.add_argument(
        "--ignoretimeouts", action="store_true", help="Continue in case of timeouts"
    )

    subparsers = parser.add_subparsers(help="Supported devices", required=True)

    parser_a = subparsers.add_parser(
        "webconnect", help="Devices with Webconnect interface"
    )
    parser_a.add_argument("user", choices=["user", "installer"], help="Login username")
    parser_a.add_argument("password", help="Login password")
    parser_a.add_argument("url", type=str, help="Url or IP-Address")
    parser_a.set_defaults(accessmethod="webconnect")

    parser_b = subparsers.add_parser(
        "speedwire", help="Devices with Speedwire interface (unencrypted only)"
    )
    parser_b.add_argument("user", choices=["user", "installer"], help="Login username")
    parser_b.add_argument("password", help="Login password")
    parser_b.add_argument("url", type=str, help="Url or IP-Address")
    parser_b.set_defaults(accessmethod="speedwireinv")

    parser_sw2 = subparsers.add_parser(
        "speedwirenew", help="Devices with Speedwire interface (unencrypted only)"
    )
    parser_sw2.add_argument(
        "user", choices=["user", "installer"], help="Login username"
    )
    parser_sw2.add_argument("password", help="Login password")
    parser_sw2.add_argument("url", type=str, help="Url or IP-Address")
    parser_sw2.set_defaults(accessmethod="speedwireinvV2")

    parser_c = subparsers.add_parser("ennexos", help="EnnexOs based Devices")
    parser_c.set_defaults(accessmethod="ennexos")
    parser_c.add_argument("user", help="Username")
    parser_c.add_argument("password", help="Login password")
    parser_c.add_argument("url", type=str, help="Hostname or IP-Address")

    parser_d = subparsers.add_parser("energymeter", help="Energy Meters")
    parser_d.set_defaults(user="")
    parser_d.set_defaults(password="")
    parser_d.set_defaults(url="")
    parser_d.set_defaults(accessmethod="speedwireem")

    parser_h = subparsers.add_parser(
        "shm2", help="Sunny Home Manager, optionally with Grid Guard Code"
    )
    parser_h.set_defaults(user="")
    parser_h.set_defaults(password="")
    parser_h.add_argument("url", type=str, help="IP-Address")
    parser_h.add_argument("password", type=str, help="Grid Guard Code", nargs="?")
    parser_h.set_defaults(accessmethod="shm2")

    parser_e = subparsers.add_parser(
        "identify", help="Tries to identify the available interfaces"
    )
    parser_e.add_argument("url", type=str, help="Hostname or IP-Address")
    parser_e.set_defaults(accessmethod="identify")

    parser_f = subparsers.add_parser("discovery", help="Tries to discovery SMA Devices")
    parser_f.set_defaults(accessmethod="discovery")
    parser_f.add_argument(
        "-i",
        "--identify",
        action="store_true",
        help="Run identify on found IP-addresses",
    )

    parser_g = subparsers.add_parser("semp", help="Semp Demo")
    parser_g.set_defaults(accessmethod="sempdemo")
    # parser_g.set_defaults(user="")
    # parser_g.set_defaults(password="")
    # parser_g.set_defaults(url="")

    for p in [parser_a, parser_b, parser_c, parser_d, parser_sw2, parser_h]:
        p.add_argument(
            "--set",
            metavar="KEY=VALUE",
            nargs="+",
            help="Set Parameters",
        )
        p.add_argument(
            "-o",
            "--options",
            metavar="KEY=VALUE",
            nargs="+",
            help="Set module specific options",
        )
    args = parser.parse_args(args=None if sys.argv[1:] else ["--help"])

    setupLogging(args.verbose)

    if args.accessmethod == "identify":
        print("Energy Meters are not identified using this method.\n")
        print("Identification can take up to 30 seconds...\n")
        await identify(args.url, args.save)

    elif args.accessmethod == "discovery":
        print("Discovery...\n")
        await discovery(args.save, args.identify)

    elif args.accessmethod == "sempdemo":
        await sempdemo()

    else:

        def _shutdown(*_):
            VAR["running"] = False

        signal.signal(signal.SIGINT, _shutdown)
        await main_loop(args)


if __name__ == "__main__":
    asyncio.run(main())
