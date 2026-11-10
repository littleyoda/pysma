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
