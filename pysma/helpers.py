"""Helper functions for the pysma library."""

import asyncio
import dataclasses
import json
import logging
import socket
from typing import Any, Dict, Optional
from urllib.parse import urlparse

_LOGGER = logging.getLogger(__name__)

SPEEDWIRE_PORT = 9522


class BetterJSONEncoder(json.JSONEncoder):
    """JSON Encoder that handles dataclasses and non serialziable objects."""

    def default(self, o: Any) -> Any:
        """Handler for the Encoder."""
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return str(o)


def splitUrl(url: str, fallbackScheme: str = "fake") -> Dict[str, Any]:
    url = url.strip(" ")
    if "://" not in url:
        url = fallbackScheme + "://" + url
    x = urlparse(url)
    return {
        "schema": x.scheme,
        "host": x.hostname,
        "netloc": x.netloc,
        "port": x.port,
    }


def toJson(obj: Any):
    """Converts a object to a json String.
    Incl. handling of dataclass."""
    return json.dumps(obj, cls=BetterJSONEncoder, indent=4)


def version_int_to_string(version_integer: int) -> str:
    """Convert a version integer to a readable string.

    Args:
        version_integer (int): The version integer, as retrieved from the device.

    Returns:
        str: The version translated to a readable string.
    """
    if not version_integer:
        return ""

    appendixes = ["N", "E", "A", "B", "R", "S"]
    version_bytes = version_integer.to_bytes(4, "big")
    version_appendix = (
        appendixes[version_bytes[3]] if 0 <= version_bytes[3] < len(appendixes) else ""
    )
    return f"{version_bytes[0]:x}.{version_bytes[1]:x}.{version_bytes[2]}.{version_appendix}"


def isInteger(s: str) -> bool:
    """Test if the string is a integer"""
    try:
        int(s)
        return True
    except ValueError:
        return False


async def create_speedwire_socket(
    host: str, port: int = SPEEDWIRE_PORT
) -> Optional[socket.socket]:
    """Create a UDP socket bound to local port 9522 and connected to host.

    Some older Speedwire devices (e.g. Sunny Boy Smart Energy SB 3600SE-10)
    only answer requests whose UDP source port is 9522; requests sent from an
    ephemeral port are silently ignored. Sunny Explorer always uses 9522.

    SO_REUSEADDR allows sharing the port with other Speedwire sockets (e.g. the
    Energy Meter multicast listener). The socket is connected, so the kernel
    delivers the device's replies to this socket and not to other listeners.

    Returns None if the socket cannot be set up, so callers can fall back to an
    ephemeral source port (previous behaviour).
    """
    loop = asyncio.get_running_loop()
    sock: Optional[socket.socket] = None
    try:
        infos = await loop.getaddrinfo(
            host, port, family=socket.AF_INET, type=socket.SOCK_DGRAM
        )
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", SPEEDWIRE_PORT))
        sock.connect(infos[0][4])
        sock.setblocking(False)
        return sock
    except OSError as err:
        _LOGGER.debug(
            "Cannot use local port %s for %s (%s), using ephemeral port",
            SPEEDWIRE_PORT,
            host,
            err,
        )
        if sock is not None:
            sock.close()
        return None
