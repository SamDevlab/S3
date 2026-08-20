"""Provider-backed bounded TLS server boundary for M1.94."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time
from typing import Protocol

from .async_core import AsyncErrorCode, AsyncFuture, AsyncFrame, complete, fail, pending
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
    max_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not isinstance(self.certificate, str) or not self.certificate or "\x00" in self.certificate:
            raise ValueError("TLS server certificate identity is required")
        if not isinstance(self.private_key, str) or not self.private_key or "\x00" in self.private_key:
            raise ValueError("TLS server private-key identity is required")
        values = (self.max_connections, self.max_read_write)
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            raise ValueError("TLS server limits must be positive integers")
        if isinstance(self.max_timeout_seconds, bool) or not isinstance(self.max_timeout_seconds, (int, float)) or not 0 < self.max_timeout_seconds <= 300:
            raise ValueError("TLS server timeout must be within (0, 300]")


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
        self._pending_handshakes: dict[int, object] = {}
        self._next_id = 0

    @property
    def active_connections(self) -> int:
        return len(self._connections)

    @property
    def active_resources(self) -> int:
        return len(self._connections) + len(self._pending_handshakes)

    def accept(self, connection: object) -> AsyncFuture[AsyncTlsServerConnection]:
        deadline = time.monotonic() + float(self.config.max_timeout_seconds)
        if self.active_resources >= self.config.max_connections:
            try:
                self.provider.close(connection)
            except Exception:
                pass
            return AsyncFuture(
                lambda _frame: fail(
                    AsyncErrorCode.FRAME_LIMIT,
                    "accept",
                    "TLS server connection limit exceeded",
                )
            )
        if self._next_id >= (1 << 63) - 1:
            try:
                self.provider.close(connection)
            except Exception:
                pass
            return AsyncFuture(
                lambda _frame: fail(
                    AsyncErrorCode.FRAME_LIMIT,
                    "accept",
                    "TLS connection identifier limit exceeded",
                )
            )
        identifier = self._next_id
        self._next_id += 1
        self._pending_handshakes[identifier] = connection
        frame_owned = False
        transferred = False
        resource_closed = False

        def close_provider_resource() -> None:
            nonlocal resource_closed
            if resource_closed:
                return
            resource_closed = True
            try:
                self.provider.close(connection)
            except Exception:
                pass

        def release_pending() -> None:
            self._pending_handshakes.pop(identifier, None)

        def close_unowned() -> None:
            if frame_owned or transferred or resource_closed:
                return
            close_provider_resource()

        def step(frame: AsyncFrame):
            nonlocal frame_owned, transferred
            if time.monotonic() >= deadline:
                release_pending()
                close_unowned()
                return fail(AsyncTlsServerErrorCode.TIMEOUT, "accept", "TLS handshake deadline expired")
            if "tls-server-connection" not in frame.slots:
                owned = frame.own("tls-server-connection", connection, lambda _resource: close_provider_resource())
                if owned.is_err:
                    release_pending()
                    close_unowned()
                    return fail(AsyncTlsServerErrorCode.IO, "accept", "TLS frame slot unavailable")
                frame_owned = True
            try:
                outcome = self.provider.handshake(connection, self.config.certificate, self.config.private_key)
            except Exception as error:
                release_pending()
                close_unowned()
                return fail(AsyncTlsServerErrorCode.IO, "accept", f"TLS handshake failed: {type(error).__name__}")
            if isinstance(outcome, (ServerWantRead, ServerWantWrite)):
                return pending()
            if isinstance(outcome, ServerFailure):
                release_pending()
                close_unowned()
                return fail(outcome.error.code, "accept", outcome.error.detail)
            if not isinstance(outcome, ServerReady):
                release_pending()
                close_unowned()
                return fail(AsyncTlsServerErrorCode.IO, "accept", "provider returned invalid handshake outcome")
            moved = frame.move("tls-server-connection")
            if moved.is_err:
                release_pending()
                close_unowned()
                return fail(AsyncTlsServerErrorCode.IO, "accept", "TLS connection transfer failed")
            transferred = True
            frame_owned = False
            release_pending()
            handle = AsyncTlsServerConnection(identifier, moved.value_or(None), self)
            self._connections[identifier] = handle
            return complete(handle)

        # The frame owns provider cleanup; the cancellation hook releases the
        # reserved capacity before AsyncFrame.cancel closes the resource.
        return AsyncFuture(step, cancel_hook=lambda: (release_pending(), close_unowned()))

    def read(self, connection: AsyncTlsServerConnection, amount: int) -> AsyncFuture[bytes]:
        checked = self._check(connection, "read")
        if checked is not None or isinstance(amount, bool) or not isinstance(amount, int) or not 0 < amount <= self.config.max_read_write:
            error = checked or AsyncTlsServerError(AsyncTlsServerErrorCode.IO, "read", "read amount exceeds TLS server limit")
            return AsyncFuture(lambda _frame: fail(error.code, error.operation, error.detail))
        return self._io_future("read", lambda: self.provider.read(connection.resource, amount), connection)

    def write(self, connection: AsyncTlsServerConnection, data: bytes) -> AsyncFuture[int]:
        checked = self._check(connection, "write")
        if checked is not None or not isinstance(data, bytes) or not 0 < len(data) <= self.config.max_read_write:
            error = checked or AsyncTlsServerError(AsyncTlsServerErrorCode.IO, "write", "write data exceeds TLS server limit")
            return AsyncFuture(lambda _frame: fail(error.code, error.operation, error.detail))
        return self._io_future("write", lambda: self.provider.write(connection.resource, data), connection)

    def close(self, connection: AsyncTlsServerConnection) -> Result[None, AsyncTlsServerError]:
        current = self._connections.get(connection.identifier)
        if current is None or current.closed:
            return Result.ok(None)
        current.closed = True
        self._connections.pop(connection.identifier, None)
        try:
            self.provider.close(current.resource)
        except Exception as error:
            return Result.err(AsyncTlsServerError(AsyncTlsServerErrorCode.IO, "close", f"TLS provider close failed: {type(error).__name__}"))
        return Result.ok(None)

    def _io_future(self, operation: str, call, connection: AsyncTlsServerConnection):
        deadline = time.monotonic() + float(self.config.max_timeout_seconds)

        def step(_frame: AsyncFrame):
            if time.monotonic() >= deadline:
                self.close(connection)
                return fail(AsyncTlsServerErrorCode.TIMEOUT, operation, "TLS I/O deadline expired")
            try:
                outcome = call()
            except Exception as error:
                self.close(connection)
                return fail(AsyncTlsServerErrorCode.IO, operation, f"TLS provider I/O failed: {type(error).__name__}")
            if isinstance(outcome, (ServerWantRead, ServerWantWrite)):
                return pending()
            if isinstance(outcome, ServerFailure):
                self.close(connection)
                return fail(outcome.error.code, operation, outcome.error.detail)
            if isinstance(outcome, ServerReady):
                return complete(outcome.value)
            self.close(connection)
            return fail(AsyncTlsServerErrorCode.IO, operation, "provider returned invalid TLS I/O outcome")

        return AsyncFuture(step, cancel_hook=lambda: self.close(connection))

    def _check(self, connection: AsyncTlsServerConnection, operation: str) -> AsyncTlsServerError | None:
        if not isinstance(connection, AsyncTlsServerConnection) or connection.server is not self or connection.closed or connection.identifier not in self._connections:
            return AsyncTlsServerError(AsyncTlsServerErrorCode.CLOSED, operation, "TLS server connection is closed")
        return None
