from __future__ import annotations

import pytest

from bootstrap.s3.async_core import AsyncState, PollKind
from bootstrap.s3.async_network import (
    AsyncNetworkError,
    AsyncNetworkErrorCode,
    AsyncNetworkHandle,
    AsyncNetworkService,
    PendingOperation,
    PendingResource,
    ProviderFailure,
)
from bootstrap.s3.network import NetworkAddress


pytestmark = pytest.mark.s3_fast


class FixtureProvider:
    def __init__(self) -> None:
        self.closed: list[object] = []
        self.connect_calls = 0
        self._stream = object()

    def connect(self, _address):
        self.connect_calls += 1
        return PendingOperation() if self.connect_calls == 1 else self._stream

    def accept(self, _listener):
        return object()

    def read(self, _stream, _amount):
        return b"reply"

    def write(self, _stream, data):
        return len(data)

    def udp_send(self, _socket, data, _address):
        return len(data)

    def udp_receive(self, _socket):
        return (b"datagram", NetworkAddress.numeric("127.0.0.1", 9000))

    def resolve(self, _host, _port):
        return (NetworkAddress.numeric("127.0.0.1", 80),)

    def close(self, resource):
        self.closed.append(resource)


def _connect(service: AsyncNetworkService):
    future = service.connect(NetworkAddress.numeric("127.0.0.1", 9000))
    assert future.poll().kind is PollKind.PENDING
    result = future.poll()
    assert result.kind is PollKind.READY
    return result.value


def test_async_tcp_connect_read_write_and_cleanup_are_explicit() -> None:
    provider = FixtureProvider()
    service = AsyncNetworkService(provider)
    handle = _connect(service)
    assert isinstance(handle, AsyncNetworkHandle)
    read = service.read(handle, 16).poll()
    write = service.write(handle, b"hello").poll()
    assert read.value == b"reply"
    assert write.value == 5
    assert handle.close().is_ok
    assert provider.closed == [provider._stream]
    assert service.read(handle, 1).poll().error.code is AsyncNetworkErrorCode.CLOSED  # type: ignore[union-attr]


def test_async_udp_and_dns_use_local_fixture_results() -> None:
    provider = FixtureProvider()
    service = AsyncNetworkService(provider)
    handle = _connect(service)
    assert service.udp_send(handle, b"x", NetworkAddress.numeric("127.0.0.1", 9)).poll().value == 1
    datagram = service.udp_receive(handle).poll().value
    assert datagram[0] == b"datagram"
    resolved = service.resolve("localhost", 80).poll().value
    assert resolved == (NetworkAddress.numeric("127.0.0.1", 80),)
    handle.close()


def test_provider_failure_and_invalid_buffer_are_explicit() -> None:
    class FailureProvider(FixtureProvider):
        def read(self, _stream, _amount):
            return ProviderFailure(AsyncNetworkError(AsyncNetworkErrorCode.TIMEOUT, "read", "fixture timeout"))

    service = AsyncNetworkService(FailureProvider())
    handle = _connect(service)
    timeout = service.read(handle, 1).poll()
    assert timeout.kind is PollKind.FAILED
    assert timeout.error.code is AsyncNetworkErrorCode.TIMEOUT  # type: ignore[union-attr]
    invalid = service.write(handle, bytearray(b"x")).poll()
    assert invalid.error.code is AsyncNetworkErrorCode.INVALID_ARGUMENT  # type: ignore[union-attr]
    handle.close()


def test_pending_resource_is_closed_when_future_is_cancelled() -> None:
    class PendingResourceProvider(FixtureProvider):
        def __init__(self):
            super().__init__()
            self.step = 0

        def connect(self, _address):
            self.step += 1
            if self.step == 1:
                return PendingResource(self._stream)
            return PendingOperation()

    provider = PendingResourceProvider()
    service = AsyncNetworkService(provider)
    future = service.connect(NetworkAddress.numeric("127.0.0.1", 1))
    assert future.poll().kind is PollKind.PENDING
    assert future.cancel().is_ok
    assert provider.closed == [provider._stream]
    assert future.state is AsyncState.CANCELLED
