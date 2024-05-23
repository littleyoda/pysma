"""SMA WebConnect library for Python.

See: http://www.sma.de/en/products/monitoring-control/webconnect.html

Source: http://www.github.com/kellerza/pysma
"""

import asyncio
import logging
from typing import Optional

from aiohttp import ClientSession

from .device import Device
from .device_em import SMAspeedwireEM
from .device_ennexos import SMAennexos
from .device_speedwire import SMAspeedwireINV
from .device_webconnect import SMAwebconnect
from .discovery import Discovery

_LOGGER = logging.getLogger(__name__)


def SMA(session, url, password, group):
    """Backward compatibility"""
    # pylint: disable=invalid-name
    return SMAwebconnect(session, url, password=password, group=group)


def getDevice(
    session: ClientSession,
    url: str,
    password: Optional[str] = None,
    groupuser: str = "user",
    accessmethod: str = "webconnect",
) -> Device | None:
    # pylint: disable=invalid-name
    """Returns a Device object for accessing the device"""
    _LOGGER.debug(
        "Device Called! Url: %s User/Group: %s Accessmethod: %s",
        url,
        groupuser,
        accessmethod,
    )
    if accessmethod == "webconnect":
        return SMAwebconnect(session, url, password=password, group=groupuser)
    if accessmethod == "ennexos":
        return SMAennexos(session, url, password=password, group=groupuser)
    if accessmethod in ["speedwire", "speedwireem"]:
        return SMAspeedwireEM()
    if accessmethod == "speedwireinv":
        return SMAspeedwireINV(host=url, password=password, group=groupuser)
    return None


async def _run_detect(accessmethod: str, session: ClientSession, ip):
    """Start Autodetection"""
    sma: Device
    if accessmethod == "webconnect":
        sma = SMAwebconnect(session, ip, password="", group="user")
    elif accessmethod == "ennexos":
        sma = SMAennexos(session, ip, password=None, group=None)
    elif accessmethod == "speedwireinv":
        sma = SMAspeedwireINV(host=ip, password="", group="user")
    else:
        return None
    ret = await sma.detect(ip)
    for i in ret:
        i["access"] = accessmethod
    try:
        await sma.close_session()
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return ret


async def autoDetect(session: ClientSession, ip: str):
    # pylint: disable=invalid-name
    """Runs a autodetection of all supported devices (no energy meters) on the ip-address"""
    ret = await asyncio.gather(
        _run_detect("ennexos", session, ip),
        _run_detect("speedwireinv", session, ip),
        _run_detect("webconnect", session, ip),
    )
    results = []
    for r in ret:
        results.extend(r)
    return results


async def discovery():
    discover = Discovery(asyncio.get_event_loop())
    return await discover.run()
