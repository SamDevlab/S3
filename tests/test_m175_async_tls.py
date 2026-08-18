from __future__ import annotations

import pytest

from bootstrap.s3.async_core import PollKind
from bootstrap.s3.async_tls import (
    AsyncTlsClient,
    AsyncTlsConfig,
    AsyncTlsError,
    AsyncTlsErrorCode,
    AsyncTlsService,
    Failure,
    Ready,
    WantRead,
    WantWrite,
)


pytestmark = pytest.mark.s3_fast


class FixtureTlsProvider:
    def __init__(self, handshake_outcomes):
        self.handshake_outcomes = list(handshake_outcomes)
        self.closed: list[object] = []
        self.io_outcomes: list[object] = [Ready(b"reply")]

    def handshake(self, connection, _hostname):
        del connection
        return self.handshake_outcomes.pop(0)

    def read(self, _connection, _amount):
        return self.io_outcomes.pop(0)

    def write(self, _connection, data):
        return Ready(len(data))

    def close(self, connection):
        self.closed.append(connection)


def test_handshake_want_states_are_nonblocking_and_validation_is_on() -> None:
    provider = FixtureTlsProvider([WantRead(), WantWrite(), Ready(True)])
    service = AsyncTlsService(provider)
    client_future = service.handshake(object(), AsyncTlsConfig("fixture.test"))
    assert client_future.poll().kind is PollKind.PENDING
    assert client_future.poll().kind is PollKind.PENDING
    result = client_future.poll()
    assert result.kind is PollKind.READY
    assert isinstance(result.value, AsyncTlsClient)
    assert result.value.config.verify_certificate is True
    assert result.value.config.verify_hostname is True


def test_certificate_and_hostname_validation_cannot_be_disabled() -> None:
    with pytest.raises(ValueError):
        AsyncTlsConfig("fixture.test", verify_certificate=False)
    with pytest.raises(ValueError):
        AsyncTlsConfig("fixture.test", verify_hostname=False)


def test_hostname_or_certificate_failure_closes_pending_connection() -> None:
    connection = object()
    provider = FixtureTlsProvider([Failure(AsyncTlsError(AsyncTlsErrorCode.HOSTNAME, "handshake", "mismatch"))])
    future = AsyncTlsService(provider).handshake(connection, AsyncTlsConfig("fixture.test"))
    result = future.poll()
    assert result.kind is PollKind.FAILED
    assert result.error.code is AsyncTlsErrorCode.HOSTNAME  # type: ignore[union-attr]
    assert provider.closed == [connection]


def test_cancelled_handshake_closes_connection_and_io_is_bounded() -> None:
    connection = object()
    provider = FixtureTlsProvider([WantRead()])
    future = AsyncTlsService(provider).handshake(connection, AsyncTlsConfig("fixture.test", max_read_write=4))
    assert future.poll().kind is PollKind.PENDING
    assert future.cancel().is_ok
    assert provider.closed == [connection]

    ready_provider = FixtureTlsProvider([Ready(True)])
    client = AsyncTlsService(ready_provider).handshake(object(), AsyncTlsConfig("fixture.test", max_read_write=4)).poll().value
    assert isinstance(client, AsyncTlsClient)
    assert client.write(b"12345").poll().error.code is AsyncTlsErrorCode.RESOURCE_LIMIT  # type: ignore[union-attr]
    assert client.close().is_ok
    assert client.close().is_ok
