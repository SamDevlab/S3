"""Non-blocking TLS state-machine contract for S3 M1.75."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .async_core import AsyncFuture, AsyncFrame, complete, fail, pending
from .results import Result


class AsyncTlsErrorCode(Enum):
    INVALID_CONFIG = "invalid_config"
    CERTIFICATE = "certificate"
    HOSTNAME = "hostname"
    TIMEOUT = "timeout"
    IO = "io"
    CLOSED = "closed"
    RESOURCE_LIMIT = "resource_limit"


@dataclass(frozen=True, slots=True)
class AsyncTlsError:
    code: AsyncTlsErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class WantRead:
    pass


@dataclass(frozen=True, slots=True)
class WantWrite:
    pass


@dataclass(frozen=True, slots=True)
class Ready:
    value: object


@dataclass(frozen=True, slots=True)
class Failure:
    error: AsyncTlsError


class AsyncTlsProvider(Protocol):
    def handshake(self, connection: object, hostname: str) -> object: ...
    def read(self, connection: object, amount: int) -> object: ...
    def write(self, connection: object, data: bytes) -> object: ...
    def close(self, connection: object) -> None: ...


@dataclass(frozen=True, slots=True)
class AsyncTlsConfig:
    hostname: str
    verify_certificate: bool = True
    verify_hostname: bool = True
    max_read_write: int = 65_536

    def __post_init__(self) -> None:
        if not isinstance(self.hostname, str) or not self.hostname or "\x00" in self.hostname:
            raise ValueError("TLS hostname must be non-empty and NUL-free")
        if self.verify_certificate is not True or self.verify_hostname is not True:
            raise ValueError("TLS certificate and hostname validation cannot be disabled")
        if isinstance(self.max_read_write, bool) or not isinstance(self.max_read_write, int) or self.max_read_write <= 0:
            raise ValueError("TLS max_read_write must be positive")


class AsyncTlsClient:
    def __init__(self, provider: AsyncTlsProvider, connection: object, config: AsyncTlsConfig) -> None:
        self._provider = provider
        self._connection = connection
        self.config = config
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def read(self, amount: int) -> AsyncFuture[bytes]:
        if self._closed or isinstance(amount, bool) or not isinstance(amount, int) or not 0 < amount <= self.config.max_read_write:
            error = AsyncTlsError(AsyncTlsErrorCode.CLOSED if self._closed else AsyncTlsErrorCode.RESOURCE_LIMIT, "read", "TLS client is closed or amount is invalid")
            return AsyncFuture(lambda _frame: fail(error.code, error.operation, error.detail))
        return _io_future("read", lambda: self._provider.read(self._connection, amount))

    def write(self, data: bytes) -> AsyncFuture[int]:
        if self._closed or not isinstance(data, bytes) or not 0 < len(data) <= self.config.max_read_write:
            error = AsyncTlsError(AsyncTlsErrorCode.CLOSED if self._closed else AsyncTlsErrorCode.RESOURCE_LIMIT, "write", "TLS client is closed or data is invalid")
            return AsyncFuture(lambda _frame: fail(error.code, error.operation, error.detail))
        return _io_future("write", lambda: self._provider.write(self._connection, data))

    def close(self) -> Result[None, AsyncTlsError]:
        if self._closed:
            return Result.ok(None)
        self._provider.close(self._connection)
        self._closed = True
        return Result.ok(None)


class AsyncTlsService:
    def __init__(self, provider: AsyncTlsProvider) -> None:
        self.provider = provider

    def handshake(self, connection: object, config: AsyncTlsConfig) -> AsyncFuture[AsyncTlsClient]:
        def step(frame: AsyncFrame):
            if "tls-connection" not in frame.slots:
                owned = frame.own("tls-connection", connection, self.provider.close)
                if owned.is_err:
                    return fail(AsyncTlsErrorCode.RESOURCE_LIMIT, "handshake", "TLS frame slot unavailable")
            outcome = self.provider.handshake(connection, config.hostname)
            if isinstance(outcome, (WantRead, WantWrite)):
                return pending()
            if isinstance(outcome, Failure):
                return fail(outcome.error.code, "handshake", outcome.error.detail)
            if not isinstance(outcome, Ready):
                return fail(AsyncTlsErrorCode.IO, "handshake", "provider returned invalid handshake outcome")
            moved = frame.move("tls-connection")
            if moved.is_err:
                return fail(AsyncTlsErrorCode.IO, "handshake", "TLS connection transfer failed")
            return complete(AsyncTlsClient(self.provider, moved.value_or(None), config))

        return AsyncFuture(step)


def _io_future(operation: str, call):
    def step(_frame: AsyncFrame):
        outcome = call()
        if isinstance(outcome, (WantRead, WantWrite)):
            return pending()
        if isinstance(outcome, Failure):
            return fail(outcome.error.code, operation, outcome.error.detail)
        if isinstance(outcome, Ready):
            return complete(outcome.value)
        return fail(AsyncTlsErrorCode.IO, operation, "provider returned invalid I/O outcome")

    return AsyncFuture(step)
