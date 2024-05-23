""" Speedwire Discovery  """

import asyncio
import logging
import socket
import struct

from .definitions_speedwire import speedwireHeader

_LOGGER = logging.getLogger(__name__)


class Discovery:
    def __init__(self, loop):
        self.loop = loop
        self.transport = None
        self.addr = "239.12.255.254"
        self.port = 9522
        self.discovered = []

    def getDiscoverySocket(self):
        addrinfo = socket.getaddrinfo(self.addr, None)[0]
        sock = socket.socket(addrinfo[0], socket.SOCK_DGRAM)
        sock.setsockopt(
            socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack("@i", 1)
        )
        return sock

    async def run(self):
        sock = self.getDiscoverySocket()
        on_connection_lost = self.loop.create_future()
        connect = await self.loop.create_datagram_endpoint(
            lambda: self,
            sock=sock,
        )
        for i in range(0, 3):
            await asyncio.sleep(0.5)
            self.sendDiscoveryRequest()
        await asyncio.sleep(0.5)
        return self.discovered

    def connection_made(self, transport):
        self.transport = transport
        self.sendDiscoveryRequest()

    def sendDiscoveryRequest(self):
        _LOGGER.warn("Sending Discovery Request")
        self.transport.sendto(
            bytes.fromhex("534d4100000402a0ffffffff0000002000000000"),
            (self.addr, self.port),
        )

    def datagram_received(self, data, addr):
        msg = speedwireHeader.from_packed(data[0:18])
        if not msg.isDiscoveryResponse():
            _LOGGER.warn("Ignoring %", msg)
            return
        if addr not in self.discovered:
            self.discovered.append(addr)

    def error_received(self, exc):
        _LOGGER.error("Error received:", exc)

    def connection_lost(self, exc):
        print("Socket closed, stop the event loop")
