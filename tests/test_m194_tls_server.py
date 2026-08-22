from __future__ import annotations

from collections.abc import Iterable

import bootstrap.s3.async_tls_server as async_tls_server_module
from bootstrap.s3.async_core import PollKind
from bootstrap.s3.async_tls_server import (
    AsyncTlsServer,
    AsyncTlsServerConfig,
    ServerReady,
    ServerWantRead,
)


class FixtureTlsServerProvider:
    def __init__(self) -> None:
        self.handshakes = 0
        self.closed: list[object] = []

    def handshake(self, connection, certificate, private_key):
        assert certificate == "fixture-cert"
        assert private_key == "fixture-key"
        self.handshakes += 1
        return ServerWantRead() if self.handshakes == 1 else ServerReady(connection)

    def read(self, _connection, _amount):
        return ServerReady(b"request")

    def write(self, _connection, data):
        return ServerReady(len(data))

    def close(self, connection):
        self.closed.append(connection)


class PendingTlsServerProvider(FixtureTlsServerProvider):
    def handshake(self, connection, certificate, private_key):
        return ServerWantRead()


class StepClock:
    def __init__(self, values: Iterable[float]) -> None:
        self._values = iter(values)
        self._last = 0.0

    def monotonic(self) -> float:
        try:
            self._last = next(self._values)
        except StopIteration:
            pass
        return self._last


def _use_clock(monkeypatch, *values: float) -> None:
    monkeypatch.setattr(async_tls_server_module.time, "monotonic", StepClock(values).monotonic)


def test_tls_server_handshake_read_write_and_cleanup_are_explicit() -> None:
    provider = FixtureTlsServerProvider()
    server = AsyncTlsServer(provider, AsyncTlsServerConfig("fixture-cert", "fixture-key"))
    future = server.accept(object())
    assert future.poll().kind is PollKind.PENDING
    accepted = future.poll()
    assert accepted.kind is PollKind.READY
    connection = accepted.value
    assert server.active_connections == 1
    assert connection.read(16).poll().value == b"request"
    assert connection.write(b"response").poll().value == 8
    assert connection.close().is_ok
    assert provider.closed == [connection.resource]
    assert connection.read(1).poll().kind is PollKind.FAILED


def test_tls_server_rejects_missing_identity_and_connection_overflow() -> None:
    try:
        AsyncTlsServerConfig("", "key")
    except ValueError as error:
        assert "certificate" in str(error)
    else:
        raise AssertionError("missing certificate was accepted")
    provider = FixtureTlsServerProvider()
    server = AsyncTlsServer(provider, AsyncTlsServerConfig("fixture-cert", "fixture-key", max_connections=1))
    first = server.accept(object())
    assert first.poll().kind is PollKind.PENDING
    assert first.poll().kind is PollKind.READY
    second = server.accept(object()).poll()
    assert second.kind is PollKind.FAILED


def test_pending_handshakes_consume_and_release_the_connection_budget() -> None:
    provider = PendingTlsServerProvider()
    server = AsyncTlsServer(provider, AsyncTlsServerConfig("fixture-cert", "fixture-key", max_connections=1))
    first = server.accept(object())
    assert first.poll().kind is PollKind.PENDING
    assert server.active_resources == 1
    second = server.accept(object()).poll()
    assert second.kind is PollKind.FAILED
    assert server.active_resources == 1
    assert first.cancel().is_ok
    assert server.active_resources == 0
    replacement = server.accept(object())
    assert replacement.poll().kind is PollKind.PENDING
    assert replacement.cancel().is_ok
    assert server.active_resources == 0
    assert len(provider.closed) == 3


def test_tls_accept_cancellation_before_first_poll_closes_unowned_resource() -> None:
    provider = PendingTlsServerProvider()
    server = AsyncTlsServer(provider, AsyncTlsServerConfig("fixture-cert", "fixture-key", max_connections=1))
    future = server.accept(object())
    assert server.active_resources == 1
    assert future.cancel().is_ok
    assert server.active_resources == 0
    assert len(provider.closed) == 1


def test_tls_handshake_timeout_before_first_poll_releases_reserved_budget(monkeypatch) -> None:
    _use_clock(monkeypatch, 100.000, 100.002, 110.000, 110.0005)
    provider = PendingTlsServerProvider()
    server = AsyncTlsServer(provider, AsyncTlsServerConfig("fixture-cert", "fixture-key", max_connections=1, max_timeout_seconds=0.001))
    future = server.accept(object())
    assert future.poll().kind is PollKind.FAILED
    assert server.active_resources == 0
    assert server.active_connections == 0
    assert len(provider.closed) == 1

    replacement = server.accept(object())
    assert replacement.poll().kind is PollKind.PENDING
    assert replacement.cancel().is_ok
    assert server.active_resources == 0


def test_tls_handshake_timeout_after_frame_ownership_closes_once(monkeypatch) -> None:
    _use_clock(monkeypatch, 200.000, 200.0005, 200.002)
    provider = PendingTlsServerProvider()
    server = AsyncTlsServer(provider, AsyncTlsServerConfig("fixture-cert", "fixture-key", max_connections=1, max_timeout_seconds=0.001))
    connection = object()
    future = server.accept(connection)

    assert future.poll().kind is PollKind.PENDING
    assert server.active_resources == 1
    assert server.active_connections == 0

    assert future.poll().kind is PollKind.FAILED
    assert server.active_resources == 0
    assert server.active_connections == 0
    assert provider.closed.count(connection) == 1


def test_tls_handshake_deadline_not_yet_expired_remains_pending(monkeypatch) -> None:
    _use_clock(monkeypatch, 300.000, 300.0005)
    provider = PendingTlsServerProvider()
    server = AsyncTlsServer(provider, AsyncTlsServerConfig("fixture-cert", "fixture-key", max_connections=1, max_timeout_seconds=0.001))
    future = server.accept(object())

    assert future.poll().kind is PollKind.PENDING
    assert server.active_resources == 1
    assert future.cancel().is_ok
    assert server.active_resources == 0
