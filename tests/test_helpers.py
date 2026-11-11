"""Test pysma helpers file."""
from pysma.helpers import version_int_to_string


def test_version_int_to_string():
    """Ensure version_int_to_string returns correct values."""
    assert version_int_to_string(4294967294) == "ff.ff.255."
    assert version_int_to_string(51387396) == "3.10.28.R"
    assert version_int_to_string(1) == "0.0.0.E"
    assert version_int_to_string(0) == ""
    assert version_int_to_string(None) == ""


async def test_create_speedwire_socket_uses_port_9522():
    """Socket is bound to local port 9522 and connected to the device."""
    from pysma.helpers import SPEEDWIRE_PORT, create_speedwire_socket

    sock = await create_speedwire_socket("127.0.0.1")
    assert sock is not None
    try:
        assert sock.getsockname()[1] == SPEEDWIRE_PORT
        assert sock.getpeername() == ("127.0.0.1", SPEEDWIRE_PORT)
    finally:
        sock.close()


async def test_create_speedwire_socket_shares_port_with_listener():
    """Port 9522 can be shared with an existing SO_REUSEADDR listener (e.g. EM)."""
    import socket

    from pysma.helpers import SPEEDWIRE_PORT, create_speedwire_socket

    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("", SPEEDWIRE_PORT))
    try:
        sock = await create_speedwire_socket("127.0.0.1")
        assert sock is not None
        sock.close()
    finally:
        listener.close()


async def test_create_speedwire_socket_fallback(monkeypatch):
    """If port 9522 cannot be used, None is returned (caller falls back)."""
    import socket

    from pysma.helpers import create_speedwire_socket

    def fail_bind(self, addr):
        raise OSError("address in use")

    monkeypatch.setattr(socket.socket, "bind", fail_bind)
    assert await create_speedwire_socket("127.0.0.1") is None


async def test_create_speedwire_socket_one_per_device():
    """Only one open socket per device may use port 9522; others fall back."""
    from pysma.helpers import SPEEDWIRE_PORT, create_speedwire_socket

    first = await create_speedwire_socket("127.0.0.1", 19522)
    assert first is not None
    try:
        assert first.getsockname()[1] == SPEEDWIRE_PORT
        # Second connection to the same device: must not share the 4-tuple
        assert await create_speedwire_socket("127.0.0.1", 19522) is None
        # A different device can still use port 9522
        other = await create_speedwire_socket("127.0.0.1", 19523)
        assert other is not None
        other.close()
    finally:
        first.close()
    # Once the first socket is closed, port 9522 is available again
    again = await create_speedwire_socket("127.0.0.1", 19522)
    assert again is not None
    again.close()


async def test_concurrent_connections_receive_own_replies():
    """Two concurrent connections to one device each get only their own replies.

    Mimics autoDetect() probing speedwireinv and speedwireinvV2 concurrently.
    """
    import asyncio
    import socket

    from pysma.helpers import create_speedwire_socket

    device = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    device.bind(("127.0.0.1", 19524))
    device.settimeout(1)

    socks = await asyncio.gather(
        create_speedwire_socket("127.0.0.1", 19524),
        create_speedwire_socket("127.0.0.1", 19524),
    )
    conns = []
    for sock in socks:
        if sock is None:  # fallback: ephemeral source port (previous behaviour)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("127.0.0.1", 19524))
        sock.settimeout(1)
        conns.append(sock)
    assert sum(s is not None for s in socks) == 1
    assert conns[0].getsockname() != conns[1].getsockname()
    try:
        for name, conn in zip((b"A", b"B"), conns):
            conn.send(b"request " + name)
            data, addr = device.recvfrom(100)
            device.sendto(b"reply " + data.split()[-1], addr)
        assert conns[0].recv(100) == b"reply A"
        assert conns[1].recv(100) == b"reply B"
    finally:
        for conn in conns:
            conn.close()
        device.close()
