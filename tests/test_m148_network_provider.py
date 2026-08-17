from __future__ import annotations

import pytest

from bootstrap.s3.network import (
    FakeNetworkProvider,
    LoopbackNetworkProvider,
    NetworkAccess,
    NetworkAddress,
    NetworkError,
    NetworkErrorCode,
    NetworkIOStatus,
    NetworkLimits,
    NetworkRegistry,
    NetworkTrace,
)


def _round_trip(registry: NetworkRegistry, port: int = 40148) -> tuple[str, list[object]]:
    address = NetworkAddress.numeric("127.0.0.1", port)
    listener_cap = registry.grant(NetworkAccess.LISTENER)
    client_cap = registry.grant(NetworkAccess.CLIENT)
    listener = registry.listen(listener_cap, address)
    client = registry.connect(client_cap, address, 1000)
    server = registry.accept(listener, 1000)
    written = registry.write(client, b"abcdef", 1000)
    first = registry.read(server, 6, 1000)
    second = registry.read(server, 6, 0)
    registry.close(client)
    eof = registry.read(server, 6, 1000)
    registry.close(server)
    registry.close(listener)
    assert written.transferred == 6
    assert first.status is NetworkIOStatus.DATA
    assert first.data == b"abcdef"
    assert second.status is NetworkIOStatus.TIMEOUT
    assert eof.status is NetworkIOStatus.EOF
    normalized = [
        (event.event, event.status, event.error_code)
        for event in registry.trace.events
    ]
    return registry.trace.as_json(), normalized


def test_numeric_address_encoding_is_normalized_and_dns_is_rejected() -> None:
    address = NetworkAddress.numeric("127.0.0.1", 80)
    assert len(address.to_bytes()) == 19
    assert NetworkAddress.from_bytes(address.to_bytes()) == address
    with pytest.raises(NetworkError) as error:
        NetworkAddress.numeric("localhost", 80)
    assert error.value.code is NetworkErrorCode.INVALID_ADDRESS


def test_fake_provider_round_trip_has_partial_io_timeout_eof_and_close() -> None:
    registry = NetworkRegistry(FakeNetworkProvider(max_chunk=64))
    trace, normalized = _round_trip(registry)
    assert '"event":"listen"' in trace
    assert normalized.count(("timeout", "timeout", int(NetworkErrorCode.TIMEOUT))) == 1
    assert normalized.count(("eof", "eof", int(NetworkErrorCode.EOF))) == 1
    assert normalized[-4:] == [
        ("close", "ok", None),
        ("eof", "eof", int(NetworkErrorCode.EOF)),
        ("close", "ok", None),
        ("close", "ok", None),
    ]


def test_fake_provider_reports_bounded_partial_write_and_read() -> None:
    registry = NetworkRegistry(FakeNetworkProvider(max_chunk=2))
    address = NetworkAddress.numeric("127.0.0.1", 40153)
    listener = registry.listen(registry.grant(NetworkAccess.LISTENER), address)
    client = registry.connect(registry.grant(NetworkAccess.CLIENT), address, 1)
    server = registry.accept(listener, 1)
    assert registry.write(client, b"abcdef", 1).transferred == 2
    result = registry.read(server, 6, 1)
    assert result.data == b"ab"
    assert result.transferred == 2
    registry.close(client)
    registry.close(server)
    registry.close(listener)


def test_capability_denial_and_use_after_close_are_explicit() -> None:
    trace = NetworkTrace()
    registry = NetworkRegistry(FakeNetworkProvider(), trace=trace)
    address = NetworkAddress.numeric("127.0.0.1", 40149)
    with pytest.raises(NetworkError) as denied:
        registry.connect(object(), address, 1)
    assert denied.value.code is NetworkErrorCode.CAPABILITY_DENIED
    listener = registry.listen(registry.grant(NetworkAccess.LISTENER), address)
    registry.close(listener)
    registry.close(listener)
    with pytest.raises(NetworkError) as closed:
        registry.accept(listener, 1)
    assert closed.value.code is NetworkErrorCode.CLOSED_HANDLE
    assert any(event.event == "capability_denied" for event in trace.events)


def test_limits_are_checked_before_unbounded_network_operations() -> None:
    limits = NetworkLimits(max_read_write=3, max_trace_entries=32)
    registry = NetworkRegistry(FakeNetworkProvider(), limits=limits)
    address = NetworkAddress.numeric("127.0.0.1", 40150)
    listener = registry.listen(registry.grant(NetworkAccess.LISTENER), address)
    client = registry.connect(registry.grant(NetworkAccess.CLIENT), address, 1)
    with pytest.raises(NetworkError) as error:
        registry.write(client, b"1234", 1)
    assert error.value.code is NetworkErrorCode.RESOURCE_LIMIT
    registry.close(client)
    registry.close(listener)


def test_fake_trace_is_deterministic_for_identical_corpora() -> None:
    first = _round_trip(NetworkRegistry(FakeNetworkProvider(max_chunk=64)), port=40151)[0]
    second = _round_trip(NetworkRegistry(FakeNetworkProvider(max_chunk=64)), port=40151)[0]
    assert first == second


def test_loopback_provider_matches_fake_operation_and_status_trace() -> None:
    fake = NetworkRegistry(FakeNetworkProvider(max_chunk=64))
    _fake_trace, fake_normalized = _round_trip(fake, port=40152)

    loopback = NetworkRegistry(LoopbackNetworkProvider())
    address = NetworkAddress.numeric("127.0.0.1", 0)
    listener = loopback.listen(loopback.grant(NetworkAccess.LISTENER), address)
    bound = loopback.bound_address(listener)
    client = loopback.connect(loopback.grant(NetworkAccess.CLIENT), bound, 1000)
    server = loopback.accept(listener, 1000)
    loopback.write(client, b"abcdef", 1000)
    assert loopback.read(server, 6, 1000).data == b"abcdef"
    assert loopback.read(server, 6, 0).status is NetworkIOStatus.TIMEOUT
    loopback.close(client)
    assert loopback.read(server, 6, 1000).status is NetworkIOStatus.EOF
    loopback.close(server)
    loopback.close(listener)
    loopback_normalized = [
        (event.event, event.status, event.error_code)
        for event in loopback.trace.events
    ]
    assert loopback_normalized == fake_normalized
