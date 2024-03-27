#!/usr/bin/env python
"""Basic usage example and testing of pysma."""
import argparse
import asyncio
import logging
import signal
import sys

import aiohttp

import pysma

# This example will work with Python 3.9+

_LOGGER = logging.getLogger(__name__)

VAR = {}


def print_table(sensors):
    """Print sensors formatted as table."""
    for sen in sensors:
        if sen.value is None:
            print("{:>25}".format(sen.name))
        else:
            print("{:>25}{:>15} {}".format(sen.name, str(sen.value), sen.unit))


async def main_loop(user, password, url, accessmethod):
    """Run main loop."""
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    ) as session:
        _LOGGER.debug(f"MainLoop called! Url: {url} User/Group: {user} Accessmethod: {accessmethod}")
        VAR["sma"] = pysma.getDevice(session, url, password, user, accessmethod)
        print(type(VAR["sma"]))
        try:
            await VAR["sma"].new_session()
        except pysma.exceptions.SmaAuthenticationException:
            _LOGGER.warning("Authentication failed!")
            return
        except pysma.exceptions.SmaConnectionException:
            _LOGGER.warning("Unable to connect to device at %s", url)
            return

        # We should not get any exceptions, but if we do we will close the session.
        try:
            VAR["running"] = True
            cnt = 5
            sensors = await VAR["sma"].get_sensors()
            device_info = await VAR["sma"].device_info()

            for name, value in device_info.items():
               print("{:>15}{:>25}".format(name, value))

            # enable all sensors
            for sensor in sensors:
                sensor.enabled = True

            while VAR.get("running"):
                await VAR["sma"].read(sensors)
                print_table(sensors)
                cnt -= 1
                if cnt == 0:
                    break
                await asyncio.sleep(2)
        finally:
            _LOGGER.info("Closing Session...")
            await VAR["sma"].close_session()


async def main():
    """Run example."""
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    parser = argparse.ArgumentParser(description="Test the SMA webconnect library.")
    parser.add_argument(
        "url",
        type=str,
        help="Web address of the Webconnect module (http://ip-address or https://ip-address)",
    )
#    parser.add_argument("user", choices=["user", "installer"], help="Login username")
    parser.add_argument("user", help="Login Group- or Username (user or installer for Webconnect)")
    parser.add_argument("password", help="Login password")
    parser.add_argument("access", choices=["webconnect", "ennexos"], help="Login password")

    args = parser.parse_args()

    def _shutdown(*_):
        VAR["running"] = False

    signal.signal(signal.SIGINT, _shutdown)

    await main_loop(user=args.user, password=args.password, url=args.url, accessmethod=args.access)


if __name__ == "__main__":
    asyncio.run(main())
