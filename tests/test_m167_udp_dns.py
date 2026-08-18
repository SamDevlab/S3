from __future__ import annotations

from bootstrap.s3.network import NetworkAddress
from bootstrap.s3.udp_dns import DnsResolver, UdpErrorCode, UdpSocket


def test_udp_loopback_send_receive_and_close() -> None:
    receiver_result = UdpSocket.bind(NetworkAddress.numeric("127.0.0.1", 0), max_datagram=64)
    sender_result = UdpSocket.bind(NetworkAddress.numeric("127.0.0.1", 0), max_datagram=64)
    assert receiver_result.is_ok and sender_result.is_ok
    receiver = receiver_result.value_or(None)
    sender = sender_result.value_or(None)
    assert receiver is not None and sender is not None
    try:
        address = receiver.bound_address().value_or(None)
        assert address is not None and address.port != 0
        assert sender.send_to(b"hello", address, 1000).value_or(-1) == 5
        datagram = receiver.receive(1000).value_or(None)
        assert datagram is not None
        assert datagram.data == b"hello"
        assert datagram.address.host == "127.0.0.1"
    finally:
        sender.close()
        receiver.close()
        receiver.close()
    assert sender.closed and receiver.closed


def test_udp_timeout_invalid_address_and_bounded_payload_are_explicit() -> None:
    socket_result = UdpSocket.bind(NetworkAddress.numeric("127.0.0.1", 0), max_datagram=4)
    assert socket_result.is_ok
    owned = socket_result.value_or(None)
    assert owned is not None
    try:
        timeout = owned.receive(1).error_or(None)
        assert timeout.code is UdpErrorCode.TIMEOUT
        oversized = owned.send_to(b"12345", NetworkAddress.numeric("127.0.0.1", 9), 1).error_or(None)
        assert oversized.code is UdpErrorCode.RESOURCE_LIMIT
        invalid_address = owned.send_to(b"x", object(), 1).error_or(None)
        assert invalid_address.code is UdpErrorCode.INVALID_ADDRESS
    finally:
        owned.close()
    closed = owned.receive(1).error_or(None)
    assert closed.code is UdpErrorCode.CLOSED


def test_dns_localhost_is_sorted_and_deduplicated() -> None:
    result = DnsResolver().resolve("localhost", 53)
    assert result.is_ok
    addresses = result.value_or(())
    assert addresses
    assert addresses == tuple(sorted(addresses, key=lambda item: (item.family.tag, item.host, item.port)))
    assert len({address.to_bytes() for address in addresses}) == len(addresses)


def test_dns_failure_and_port_validation_are_explicit() -> None:
    missing = DnsResolver().resolve("s3.invalid", 53).error_or(None)
    assert missing.code is UdpErrorCode.DNS_FAILURE
    invalid = DnsResolver().resolve("localhost", 70000).error_or(None)
    assert invalid.code is UdpErrorCode.INVALID_ADDRESS
