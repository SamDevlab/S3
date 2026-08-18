"""Vetted blocking TLS client provider for M1.68."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import socket
import ssl
from typing import Callable

from .results import Result


class TlsErrorCode(Enum):
    INVALID_ADDRESS = "invalid_address"
    INVALID_DATA = "invalid_data"
    TIMEOUT = "timeout"
    CERTIFICATE = "certificate"
    HOSTNAME = "hostname"
    CONNECTION = "connection"
    IO = "io"
    CLOSED = "closed"
    PROVIDER_MISSING = "provider_missing"


@dataclass(frozen=True, slots=True)
class TlsError:
    code: TlsErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class TlsClientConfig:
    timeout_ms: int = 10_000
    max_read_write: int = 65_536
    minimum_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2
    maximum_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_3

    def __post_init__(self) -> None:
        if isinstance(self.timeout_ms, bool) or not isinstance(self.timeout_ms, int) or self.timeout_ms < 0:
            raise ValueError("TLS timeout must be a non-negative integer")
        if isinstance(self.max_read_write, bool) or not isinstance(self.max_read_write, int) or self.max_read_write <= 0:
            raise ValueError("TLS max_read_write must be positive")
        if self.minimum_version > self.maximum_version:
            raise ValueError("TLS minimum version must not exceed maximum version")


class TlsClient:
    """An owned TLS client with verification enabled and bounded I/O."""

    def __init__(self, connection: object, *, config: TlsClientConfig) -> None:
        self._connection = connection
        self._config = config
        self._closed = False

    @classmethod
    def connect(
        cls,
        hostname: str,
        port: int,
        *,
        config: TlsClientConfig | None = None,
        cafile: str | None = None,
        _socket_factory: Callable[..., object] | None = None,
        _context_factory: Callable[..., ssl.SSLContext] | None = None,
    ) -> Result[TlsClient, TlsError]:
        selected = config or TlsClientConfig()
        if not isinstance(hostname, str) or not hostname or "\x00" in hostname:
            return Result.err(TlsError(TlsErrorCode.INVALID_ADDRESS, "connect", "hostname is invalid"))
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            return Result.err(TlsError(TlsErrorCode.INVALID_ADDRESS, "connect", "port is outside [1, 65535]"))
        try:
            context_factory = _context_factory or ssl.create_default_context
            socket_factory = _socket_factory or socket.create_connection
            context = context_factory(cafile=cafile)
            context.minimum_version = selected.minimum_version
            context.maximum_version = selected.maximum_version
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = True
        except (AttributeError, OSError, ssl.SSLError) as error:
            return Result.err(TlsError(TlsErrorCode.PROVIDER_MISSING, "context", str(error)))
        raw: object | None = None
        try:
            raw = socket_factory((hostname, port), timeout=selected.timeout_ms / 1000)
            wrapped = context.wrap_socket(raw, server_hostname=hostname)
            return Result.ok(cls(wrapped, config=selected))
        except ssl.CertificateError as error:
            if raw is not None:
                raw.close()
            return Result.err(TlsError(TlsErrorCode.HOSTNAME, "handshake", str(error)))
        except ssl.SSLError as error:
            if raw is not None:
                raw.close()
            return Result.err(TlsError(TlsErrorCode.CERTIFICATE, "handshake", str(error)))
        except (TimeoutError, socket.timeout) as error:
            if raw is not None:
                raw.close()
            return Result.err(TlsError(TlsErrorCode.TIMEOUT, "connect", str(error)))
        except OSError as error:
            if raw is not None:
                raw.close()
            return Result.err(TlsError(TlsErrorCode.CONNECTION, "connect", str(error)))

    @staticmethod
    def provider_available() -> bool:
        return bool(getattr(ssl, "OPENSSL_VERSION", ""))

    @property
    def closed(self) -> bool:
        return self._closed

    def read(self, amount: int) -> Result[bytes, TlsError]:
        if self._closed:
            return Result.err(TlsError(TlsErrorCode.CLOSED, "read", "TLS client is closed"))
        if isinstance(amount, bool) or not isinstance(amount, int) or not 0 < amount <= self._config.max_read_write:
            return Result.err(TlsError(TlsErrorCode.INVALID_DATA, "read", "amount exceeds configured limit"))
        try:
            return Result.ok(self._connection.recv(amount))
        except (TimeoutError, socket.timeout) as error:
            return Result.err(TlsError(TlsErrorCode.TIMEOUT, "read", str(error)))
        except OSError as error:
            return Result.err(TlsError(TlsErrorCode.IO, "read", str(error)))

    def write(self, data: bytes) -> Result[int, TlsError]:
        if self._closed:
            return Result.err(TlsError(TlsErrorCode.CLOSED, "write", "TLS client is closed"))
        if not isinstance(data, bytes) or not 0 < len(data) <= self._config.max_read_write:
            return Result.err(TlsError(TlsErrorCode.INVALID_DATA, "write", "data exceeds configured limit"))
        try:
            return Result.ok(self._connection.send(data))
        except (TimeoutError, socket.timeout) as error:
            return Result.err(TlsError(TlsErrorCode.TIMEOUT, "write", str(error)))
        except OSError as error:
            return Result.err(TlsError(TlsErrorCode.IO, "write", str(error)))

    def close(self) -> None:
        if not self._closed:
            self._connection.close()
            self._closed = True

    def __enter__(self) -> TlsClient:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close()
        return False
