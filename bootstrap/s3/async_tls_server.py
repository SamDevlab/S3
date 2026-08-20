"""Provider-backed bounded TLS server boundary for M1.94."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .async_core import AsyncFuture, AsyncFrame, complete, fail, pending
from .results import Result


class AsyncTlsServerErrorCode(Enum):
    INVALID_CONFIG = "invalid_config"
    CERTIFICATE = "certificate"
    HOSTNAME = "hostname"
    TIMEOUT = "timeout"
    IO = "io"
    CLOSED = "closed"
    CONNECTION_LIMIT = "connection_limit"


@dataclass(frozen=True, slots=True)
class AsyncTlsServerError:
    code: AsyncTlsServerErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class ServerWantRead:
    pass


@dataclass(frozen=True, slots=True)
class ServerWantWrite:
    pass


@dataclass(frozen=True, slots=True)
class ServerReady:
    value: object


@dataclass(frozen=True, slots=True)
class ServerFailure:
    error: AsyncTlsServerError


class AsyncTlsServerProvider(Protocol):
    def handshake(self, connection: object, certificate: str, private_key: str) -> object: ...
    def read(self, connection: object, amount: int) -> object: ...
    def write(self, connection: object, data: bytes) -> object: ...
    def close(self, connection: object) -> None: ...


@dataclass(frozen=True, slots=True)
class AsyncTlsServerConfig:
    certificate: str
    private_key: str
    max_connections: int = 32
    max_read_write: int = 65_536

    def __post_init__(self) -> None:
        if not isinstance(self.certificate, str) or not self.certificate or "\x00" in self.certificate:
            raise ValueError("TLS server certificate identity is required")
        if not isinstance(self.private_key, str) or not self.private_key or "\x00" in self.private_key:
            raise ValueError("TLS server private-key identity is required")
        values = (self.max_connections, self.max_read_write)
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            raise ValueError("TLS server limits must be positive integers")


@dataclass(slots=True)
class AsyncTlsServerConnection:
    identifier: int
    resource: object
    server: AsyncTlsServer
    closed: bool = False

    def read(self, amount: int) -> AsyncFuture[bytes]:
        return self.server.read(self, amount)

    def write(self, data: bytes) -> AsyncFuture[int]:
        return self.server.write(self, data)

    def close(self) -> Result[None, AsyncTlsServerError]:
        return self.server.close(self)


class AsyncTlsServer:
    def __init__(self, provider: AsyncTlsServerProvider, config: AsyncTlsServerConfig) -> None:
        self.provider = provider
        self.config = config
        self._connections: dict[int, AsyncTlsServerConnection] = {}
        self._next_id = 0

    @property
    def active_connections(self) -> int:
        return len(self._connections)

    def accept(self, connection: object) -> AsyncFuture[AsyncTlsServerConnection]:
        def step(frame: AsyncFrame):
            if len(self._connections) >= self.config.max_connections:
                return fail(AsyncTlsServerErrorCode.CONNECTION_LIMIT, "accept", "TLS server connection limit exceeded")
            if "tls-server-connection" not in frame.slots:
                owned = frame.own("tls-server-connection", connection, self.provider.close)
                if owned.is_err:
                    return fail(AsyncTlsServerErrorCode.IO, "accept", "TLS frame slot unavailable")
            outcome = self.provider.handshake(connection, self.config.certificate, self.config.private_key)
            if isinstance(outcome, (ServerWantRead, ServerWantWrite)):
                return pending()
            if isinstance(outcome, ServerFailure):
                return fail(outcome.error.code, "accept", outcome.error.detail)
            if not isinstance(outcome, ServerReady):
                return fail(AsyncTlsServerErrorCode.IO, "accept", "provider returned invalid handshake outcome")
            moved = frame.move("tls-server-connection")
            if moved.is_err:
                return fail(AsyncTlsServerErrorCode.IO, "accept", "TLS connection transfer failed")
            handle = AsyncTlsServerConnection(self._next_id, moved.value_or(None), self)
            self._next_id += 1
            self._connections[handle.identifier] = handle
            return complete(handle)

        return AsyncFuture(step)

    def read(self, connection: AsyncTlsServerConnection, amount: int) -> AsyncFuture[bytes]:
        checked = self._check(connection, "read")
        if checked is not None or isinstance(amount, bool) or not isinstance(amount, int) or not 0 < amount <= self.config.max_read_write:
            error = checked or AsyncTlsServerError(AsyncTlsServerErrorCode.IO, "read", "read amount exceeds TLS server limit")
            return AsyncFuture(lambda _frame: fail(error.code, error.operation, error.detail))
        return self._io_future("read", lambda: self.provider.read(connection.resource, amount))

    def write(self, connection: AsyncTlsServerConnection, data: bytes) -> AsyncFuture[int]:
        checked = self._check(connection, "write")
        if checked is not None or not isinstance(data, bytes) or not 0 < len(data) <= self.config.max_read_write:
            error = checked or AsyncTlsServerError(AsyncTlsServerErrorCode.IO, "write", "write data exceeds TLS server limit")
            return AsyncFuture(lambda _frame: fail(error.code, error.operation, error.detail))
        return self._io_future("write", lambda: self.provider.write(connection.resource, data))

    def close(self, connection: AsyncTlsServerConnection) -> Result[None, AsyncTlsServerError]:
        current = self._connections.get(connection.identifier)
        if current is None or current.closed:
            return Result.ok(None)
        current.closed = True
        self._connections.pop(connection.identifier, None)
        self.provider.close(current.resource)
        return Result.ok(None)

    def _io_future(self, operation: str, call):
        def step(_frame: AsyncFrame):
            outcome = call()
            if isinstance(outcome, (ServerWantRead, ServerWantWrite)):
                return pending()
            if isinstance(outcome, ServerFailure):
                return fail(outcome.error.code, operation, outcome.error.detail)
            if isinstance(outcome, ServerReady):
                return complete(outcome.value)
            return fail(AsyncTlsServerErrorCode.IO, operation, "provider returned invalid TLS I/O outcome")

        return AsyncFuture(step)

    def _check(self, connection: AsyncTlsServerConnection, operation: str) -> AsyncTlsServerError | None:
        if not isinstance(connection, AsyncTlsServerConnection) or connection.server is not self or connection.closed or connection.identifier not in self._connections:
            return AsyncTlsServerError(AsyncTlsServerErrorCode.CLOSED, operation, "TLS server connection is closed")
        return None
