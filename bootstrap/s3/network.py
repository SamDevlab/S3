"""Capability-scoped bounded TCP providers for M1.48.

The public surface intentionally contains only numeric TCP addresses, blocking
millisecond timeouts, bounded byte operations, and explicit owned handles.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import struct
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Protocol


class NetworkErrorCode(IntEnum):
    CAPABILITY_DENIED = 1
    INVALID_ADDRESS = 2
    CONNECTION_REFUSED = 3
    CONNECTION_RESET = 4
    TIMEOUT = 5
    EOF = 6
    RESOURCE_LIMIT = 7
    CLOSED_HANDLE = 8
    INVALID_STATE = 9
    HOST_FAILURE = 10


class NetworkError(RuntimeError):
    """Closed network error with a stable numeric code."""

    def __init__(self, code: NetworkErrorCode, message: str) -> None:
        self.code = code
        super().__init__(message)


class NetworkFamily(Enum):
    IPV4 = (4, 4)
    IPV6 = (6, 6)

    @property
    def tag(self) -> int:
        return self.value[0]


class NetworkAccess(Enum):
    CLIENT = "client"
    LISTENER = "listener"


class NetworkHandleKind(Enum):
    LISTENER = "listener"
    STREAM = "stream"


class NetworkIOStatus(Enum):
    DATA = "data"
    TIMEOUT = "timeout"
    EOF = "eof"


@dataclass(frozen=True, slots=True)
class NetworkAddress:
    """Normalized numeric address: family tag, 16-byte address, port."""

    family: NetworkFamily
    packed: bytes
    port: int

    def __post_init__(self) -> None:
        if not isinstance(self.family, NetworkFamily):
            raise NetworkError(NetworkErrorCode.INVALID_ADDRESS, "invalid address family")
        if not isinstance(self.packed, bytes) or len(self.packed) != 16:
            raise NetworkError(NetworkErrorCode.INVALID_ADDRESS, "address must contain 16 bytes")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 0 <= self.port <= 65535:
            raise NetworkError(NetworkErrorCode.INVALID_ADDRESS, "port is outside [0, 65535]")

    @classmethod
    def numeric(cls, host: str, port: int) -> "NetworkAddress":
        if not isinstance(host, str) or not host:
            raise NetworkError(NetworkErrorCode.INVALID_ADDRESS, "numeric address is required")
        try:
            address = ipaddress.ip_address(host)
        except ValueError as error:
            raise NetworkError(NetworkErrorCode.INVALID_ADDRESS, "DNS names are not accepted") from error
        if isinstance(address, ipaddress.IPv4Address):
            return cls(NetworkFamily.IPV4, b"\x00" * 10 + b"\xff\xff" + address.packed, port)
        return cls(NetworkFamily.IPV6, address.packed, port)

    @property
    def host(self) -> str:
        if self.family is NetworkFamily.IPV4:
            return str(ipaddress.IPv4Address(self.packed[-4:]))
        return str(ipaddress.IPv6Address(self.packed))

    def to_bytes(self) -> bytes:
        return bytes((self.family.tag,)) + self.packed + struct.pack(">H", self.port)

    @classmethod
    def from_bytes(cls, payload: bytes) -> "NetworkAddress":
        if len(payload) != 19:
            raise NetworkError(NetworkErrorCode.INVALID_ADDRESS, "encoded address must contain 19 bytes")
        try:
            family = next(item for item in NetworkFamily if item.tag == payload[0])
        except StopIteration as error:
            raise NetworkError(NetworkErrorCode.INVALID_ADDRESS, "unknown address family") from error
        return cls(family, payload[1:17], struct.unpack(">H", payload[17:])[0])


@dataclass(frozen=True, slots=True)
class NetworkLimits:
    max_listeners: int = 4
    max_connections: int = 16
    max_outstanding_handles: int = 32
    max_read_write: int = 65536
    max_trace_entries: int = 4096
    max_address_length: int = 64

    def __post_init__(self) -> None:
        values = (
            self.max_listeners,
            self.max_connections,
            self.max_outstanding_handles,
            self.max_read_write,
            self.max_trace_entries,
            self.max_address_length,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            raise NetworkError(NetworkErrorCode.RESOURCE_LIMIT, "network limits must be positive integers")


@dataclass(frozen=True, slots=True)
class NetworkTraceEvent:
    sequence: int
    event: str
    handle: int | None = None
    address: str | None = None
    requested: int | None = None
    transferred: int | None = None
    status: str | None = None
    error_code: int | None = None

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"sequence": self.sequence, "event": self.event}
        for name in ("handle", "address", "requested", "transferred", "status", "error_code"):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        return result


class NetworkTrace:
    """Bounded ordered trace shared by fake and native providers."""

    def __init__(self, *, max_entries: int = 4096) -> None:
        if isinstance(max_entries, bool) or not isinstance(max_entries, int) or max_entries <= 0:
            raise NetworkError(NetworkErrorCode.RESOURCE_LIMIT, "trace limit must be positive")
        self._max_entries = max_entries
        self._events: list[NetworkTraceEvent] = []

    @property
    def events(self) -> tuple[NetworkTraceEvent, ...]:
        return tuple(self._events)

    def record(self, event: str, **fields: object) -> None:
        if len(self._events) >= self._max_entries:
            raise NetworkError(NetworkErrorCode.RESOURCE_LIMIT, "network trace limit exceeded")
        self._events.append(NetworkTraceEvent(len(self._events), event, **fields))

    def as_json(self) -> str:
        return json.dumps(
            [event.as_dict() for event in self._events],
            separators=(",", ":"),
        )


@dataclass(frozen=True, slots=True)
class NetworkCapability:
    access: NetworkAccess
    _authority: object


@dataclass(frozen=True, slots=True)
class NetworkHandle:
    _registry: "NetworkRegistry"
    _identifier: int
    _kind: NetworkHandleKind

    @property
    def kind(self) -> NetworkHandleKind:
        return self._kind


@dataclass(frozen=True, slots=True)
class NetworkIOResult:
    status: NetworkIOStatus
    data: bytes = b""
    transferred: int = 0
    error_code: NetworkErrorCode | None = None

    def __post_init__(self) -> None:
        if self.status is NetworkIOStatus.DATA and self.error_code is not None:
            raise ValueError("data result cannot contain an error")
        if self.status is not NetworkIOStatus.DATA and self.data:
            raise ValueError("non-data result cannot contain bytes")


class NetworkProvider(Protocol):
    def listen(self, address: NetworkAddress) -> object:
        ...

    def connect(self, address: NetworkAddress, timeout_ms: int) -> object:
        ...

    def accept(self, listener: object, timeout_ms: int) -> object:
        ...

    def read(self, stream: object, amount: int, timeout_ms: int) -> bytes:
        ...

    def write(self, stream: object, data: bytes, timeout_ms: int) -> int:
        ...

    def close(self, resource: object) -> None:
        ...

    def bound_address(self, listener: object) -> NetworkAddress:
        ...


@dataclass(slots=True)
class _NetworkEntry:
    handle: NetworkHandle
    resource: object


class NetworkRegistry:
    """Capability-scoped registry shared by fake and loopback providers."""

    def __init__(self, provider: NetworkProvider, *, limits: NetworkLimits | None = None, trace: NetworkTrace | None = None) -> None:
        self.provider = provider
        self.limits = limits or NetworkLimits()
        self.trace = trace or NetworkTrace(max_entries=self.limits.max_trace_entries)
        self._authority = object()
        self._next_identifier = 1
        self._active: dict[int, _NetworkEntry] = {}

    def grant(self, access: NetworkAccess) -> NetworkCapability:
        if not isinstance(access, NetworkAccess):
            raise NetworkError(NetworkErrorCode.CAPABILITY_DENIED, "invalid network capability")
        return NetworkCapability(access, self._authority)

    def _require_capability(self, capability: object, access: NetworkAccess, event: str) -> None:
        if (
            not isinstance(capability, NetworkCapability)
            or capability._authority is not self._authority
            or capability.access is not access
        ):
            self.trace.record(event, status="error", error_code=int(NetworkErrorCode.CAPABILITY_DENIED))
            raise NetworkError(NetworkErrorCode.CAPABILITY_DENIED, f"{access.value} capability denied")

    def _check_timeout(self, timeout_ms: int) -> None:
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms < 0:
            raise NetworkError(NetworkErrorCode.TIMEOUT, "timeout must be a non-negative integer")

    def _check_address(self, address: NetworkAddress) -> None:
        if not isinstance(address, NetworkAddress) or len(address.host.encode("ascii")) > self.limits.max_address_length:
            raise NetworkError(NetworkErrorCode.INVALID_ADDRESS, "address exceeds active limit")

    def _check_capacity(self, kind: NetworkHandleKind) -> None:
        if len(self._active) >= self.limits.max_outstanding_handles:
            raise NetworkError(NetworkErrorCode.RESOURCE_LIMIT, "outstanding network handle limit exceeded")
        if kind is NetworkHandleKind.LISTENER and sum(entry.handle.kind is kind for entry in self._active.values()) >= self.limits.max_listeners:
            raise NetworkError(NetworkErrorCode.RESOURCE_LIMIT, "listener limit exceeded")
        if kind is NetworkHandleKind.STREAM and sum(entry.handle.kind is kind for entry in self._active.values()) >= self.limits.max_connections:
            raise NetworkError(NetworkErrorCode.RESOURCE_LIMIT, "connection limit exceeded")

    def _new_handle(self, kind: NetworkHandleKind, resource: object) -> NetworkHandle:
        self._check_capacity(kind)
        identifier = self._next_identifier
        self._next_identifier += 1
        handle = NetworkHandle(self, identifier, kind)
        self._active[identifier] = _NetworkEntry(handle, resource)
        return handle

    @staticmethod
    def _handle_id(handle: object) -> int | None:
        return handle._identifier if isinstance(handle, NetworkHandle) else None

    def listen(self, capability: object, address: NetworkAddress) -> NetworkHandle:
        self._require_capability(capability, NetworkAccess.LISTENER, "capability_denied")
        self._check_address(address)
        self._check_capacity(NetworkHandleKind.LISTENER)
        try:
            resource = self.provider.listen(address)
            handle = self._new_handle(NetworkHandleKind.LISTENER, resource)
        except NetworkError as error:
            self.trace.record("listen", address=address.host, status="error", error_code=int(error.code))
            raise
        self.trace.record("create", handle=handle._identifier)
        self.trace.record("bind", handle=handle._identifier, address=address.host)
        self.trace.record("listen", handle=handle._identifier, address=address.host, status="ok")
        return handle

    def bound_address(self, listener: NetworkHandle) -> NetworkAddress:
        entry = self._require_handle(listener, NetworkHandleKind.LISTENER, "bound")
        return self.provider.bound_address(entry.resource)

    def connect(self, capability: object, address: NetworkAddress, timeout_ms: int) -> NetworkHandle:
        self._require_capability(capability, NetworkAccess.CLIENT, "capability_denied")
        self._check_address(address)
        self._check_timeout(timeout_ms)
        self._check_capacity(NetworkHandleKind.STREAM)
        try:
            resource = self.provider.connect(address, timeout_ms)
            handle = self._new_handle(NetworkHandleKind.STREAM, resource)
        except NetworkError as error:
            self.trace.record("connect", address=address.host, status="error", error_code=int(error.code))
            raise
        self.trace.record("create", handle=handle._identifier)
        self.trace.record("connect", handle=handle._identifier, address=address.host, status="ok")
        return handle

    def accept(self, listener: NetworkHandle, timeout_ms: int) -> NetworkHandle:
        entry = self._require_handle(listener, NetworkHandleKind.LISTENER, "accept")
        self._check_timeout(timeout_ms)
        self._check_capacity(NetworkHandleKind.STREAM)
        try:
            resource = self.provider.accept(entry.resource, timeout_ms)
            handle = self._new_handle(NetworkHandleKind.STREAM, resource)
        except NetworkError as error:
            self.trace.record("accept", handle=listener._identifier, status="error", error_code=int(error.code))
            raise
        self.trace.record("accept", handle=handle._identifier, status="ok")
        return handle

    def read(self, stream: NetworkHandle, amount: int, timeout_ms: int) -> NetworkIOResult:
        entry = self._require_handle(stream, NetworkHandleKind.STREAM, "read")
        self._check_amount(amount)
        self._check_timeout(timeout_ms)
        try:
            data = self.provider.read(entry.resource, amount, timeout_ms)
        except NetworkError as error:
            if error.code in (NetworkErrorCode.TIMEOUT, NetworkErrorCode.EOF):
                status = NetworkIOStatus.TIMEOUT if error.code is NetworkErrorCode.TIMEOUT else NetworkIOStatus.EOF
                self.trace.record("timeout" if status is NetworkIOStatus.TIMEOUT else "eof", handle=stream._identifier, requested=amount, status=status.value, error_code=int(error.code))
                return NetworkIOResult(status, error_code=error.code)
            self.trace.record("read", handle=stream._identifier, requested=amount, status="error", error_code=int(error.code))
            raise
        if not data:
            self.trace.record("eof", handle=stream._identifier, requested=amount, status=NetworkIOStatus.EOF.value, error_code=int(NetworkErrorCode.EOF))
            return NetworkIOResult(NetworkIOStatus.EOF, error_code=NetworkErrorCode.EOF)
        self.trace.record("read", handle=stream._identifier, requested=amount, transferred=len(data), status=NetworkIOStatus.DATA.value)
        return NetworkIOResult(NetworkIOStatus.DATA, data=data, transferred=len(data))

    def write(self, stream: NetworkHandle, data: bytes, timeout_ms: int) -> NetworkIOResult:
        entry = self._require_handle(stream, NetworkHandleKind.STREAM, "write")
        if not isinstance(data, bytes):
            raise NetworkError(NetworkErrorCode.INVALID_STATE, "network write requires bytes")
        self._check_amount(len(data))
        self._check_timeout(timeout_ms)
        try:
            transferred = self.provider.write(entry.resource, data, timeout_ms)
        except NetworkError as error:
            if error.code is NetworkErrorCode.TIMEOUT:
                self.trace.record("timeout", handle=stream._identifier, requested=len(data), status=NetworkIOStatus.TIMEOUT.value, error_code=int(error.code))
                return NetworkIOResult(NetworkIOStatus.TIMEOUT, error_code=error.code)
            self.trace.record("write", handle=stream._identifier, requested=len(data), status="error", error_code=int(error.code))
            raise
        self.trace.record("write", handle=stream._identifier, requested=len(data), transferred=transferred, status=NetworkIOStatus.DATA.value)
        return NetworkIOResult(NetworkIOStatus.DATA, transferred=transferred)

    def close(self, handle: NetworkHandle) -> None:
        if not isinstance(handle, NetworkHandle) or handle._registry is not self:
            self.trace.record("close", status="error", error_code=int(NetworkErrorCode.CLOSED_HANDLE))
            raise NetworkError(NetworkErrorCode.CLOSED_HANDLE, "network handle is closed")
        entry = self._active.pop(handle._identifier, None)
        if entry is None:
            return
        try:
            self.provider.close(entry.resource)
        finally:
            self.trace.record("close", handle=handle._identifier, status="ok")

    def _require_handle(self, handle: object, kind: NetworkHandleKind, event: str) -> _NetworkEntry:
        if not isinstance(handle, NetworkHandle) or handle._registry is not self:
            self.trace.record(event, handle=self._handle_id(handle), status="error", error_code=int(NetworkErrorCode.CLOSED_HANDLE))
            raise NetworkError(NetworkErrorCode.CLOSED_HANDLE, "network handle is closed")
        entry = self._active.get(handle._identifier)
        if entry is None or entry.handle.kind is not kind:
            self.trace.record(event, handle=handle._identifier, status="error", error_code=int(NetworkErrorCode.CLOSED_HANDLE))
            raise NetworkError(NetworkErrorCode.CLOSED_HANDLE, "network handle is closed")
        return entry

    def _check_amount(self, amount: int) -> None:
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0 or amount > self.limits.max_read_write:
            raise NetworkError(NetworkErrorCode.RESOURCE_LIMIT, "read/write amount exceeds active limit")


@dataclass(slots=True)
class _FakeListener:
    address: NetworkAddress
    pending: list["_FakeStream"]
    closed: bool = False


@dataclass(slots=True)
class _FakeStream:
    incoming: bytearray
    closed: bool = False
    peer: "_FakeStream | None" = None


class FakeNetworkProvider:
    """Deterministic in-memory TCP stream provider used as the hosted oracle."""

    def __init__(self, *, max_chunk: int = 65536) -> None:
        if isinstance(max_chunk, bool) or not isinstance(max_chunk, int) or max_chunk <= 0:
            raise ValueError("max_chunk must be positive")
        self.max_chunk = max_chunk
        self._listeners: dict[bytes, _FakeListener] = {}

    def listen(self, address: NetworkAddress) -> _FakeListener:
        key = address.to_bytes()
        if key in self._listeners:
            raise NetworkError(NetworkErrorCode.INVALID_STATE, "address is already listening")
        listener = _FakeListener(address, [])
        self._listeners[key] = listener
        return listener

    def connect(self, address: NetworkAddress, timeout_ms: int) -> _FakeStream:
        del timeout_ms
        listener = self._listeners.get(address.to_bytes())
        if listener is None or listener.closed:
            raise NetworkError(NetworkErrorCode.CONNECTION_REFUSED, "no fake listener is bound")
        client = _FakeStream(bytearray())
        server = _FakeStream(bytearray())
        client.peer = server
        server.peer = client
        listener.pending.append(server)
        return client

    def accept(self, listener: _FakeListener, timeout_ms: int) -> _FakeStream:
        if listener.closed:
            raise NetworkError(NetworkErrorCode.CLOSED_HANDLE, "listener is closed")
        if not listener.pending:
            del timeout_ms
            raise NetworkError(NetworkErrorCode.TIMEOUT, "fake accept timed out")
        return listener.pending.pop(0)

    def read(self, stream: _FakeStream, amount: int, timeout_ms: int) -> bytes:
        if stream.closed:
            raise NetworkError(NetworkErrorCode.CONNECTION_RESET, "stream is closed")
        if stream.incoming:
            data = bytes(stream.incoming[: min(amount, self.max_chunk)])
            del stream.incoming[: len(data)]
            return data
        if stream.peer is not None and stream.peer.closed:
            raise NetworkError(NetworkErrorCode.EOF, "peer closed")
        del timeout_ms
        raise NetworkError(NetworkErrorCode.TIMEOUT, "fake read timed out")

    def write(self, stream: _FakeStream, data: bytes, timeout_ms: int) -> int:
        if stream.closed or stream.peer is None or stream.peer.closed:
            raise NetworkError(NetworkErrorCode.CONNECTION_RESET, "stream peer is closed")
        del timeout_ms
        transferred = min(len(data), self.max_chunk)
        stream.peer.incoming.extend(data[:transferred])
        return transferred

    def close(self, resource: _FakeListener | _FakeStream) -> None:
        resource.closed = True
        if isinstance(resource, _FakeListener):
            self._listeners.pop(resource.address.to_bytes(), None)

    @staticmethod
    def bound_address(listener: _FakeListener) -> NetworkAddress:
        return listener.address


@dataclass(slots=True)
class _LoopbackListener:
    socket: socket.socket
    address: NetworkAddress


class LoopbackNetworkProvider:
    """Blocking TCP provider backed by the host loopback socket API."""

    def listen(self, address: NetworkAddress) -> _LoopbackListener:
        family = socket.AF_INET if address.family is NetworkFamily.IPV4 else socket.AF_INET6
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            bind_address = (address.host, address.port)
            sock.bind(bind_address)
            sock.listen()
            actual = sock.getsockname()[1]
            return _LoopbackListener(sock, NetworkAddress.numeric(address.host, actual))
        except OSError as error:
            sock.close()
            raise NetworkError(NetworkErrorCode.HOST_FAILURE, f"loopback listen failed: {error}") from error

    def connect(self, address: NetworkAddress, timeout_ms: int) -> socket.socket:
        family = socket.AF_INET if address.family is NetworkFamily.IPV4 else socket.AF_INET6
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(timeout_ms / 1000)
        try:
            sock.connect((address.host, address.port))
            return sock
        except (TimeoutError, BlockingIOError) as error:
            sock.close()
            raise NetworkError(NetworkErrorCode.TIMEOUT, "loopback connect timed out") from error
        except ConnectionRefusedError as error:
            sock.close()
            raise NetworkError(NetworkErrorCode.CONNECTION_REFUSED, "loopback connection refused") from error
        except OSError as error:
            sock.close()
            raise NetworkError(NetworkErrorCode.HOST_FAILURE, f"loopback connect failed: {error}") from error

    def accept(self, listener: _LoopbackListener, timeout_ms: int) -> socket.socket:
        listener.socket.settimeout(timeout_ms / 1000)
        try:
            stream, _address = listener.socket.accept()
            return stream
        except (TimeoutError, BlockingIOError) as error:
            raise NetworkError(NetworkErrorCode.TIMEOUT, "loopback accept timed out") from error
        except OSError as error:
            raise NetworkError(NetworkErrorCode.HOST_FAILURE, f"loopback accept failed: {error}") from error

    def read(self, stream: socket.socket, amount: int, timeout_ms: int) -> bytes:
        stream.settimeout(timeout_ms / 1000)
        try:
            data = stream.recv(amount)
        except (TimeoutError, BlockingIOError) as error:
            raise NetworkError(NetworkErrorCode.TIMEOUT, "loopback read timed out") from error
        except ConnectionResetError as error:
            raise NetworkError(NetworkErrorCode.CONNECTION_RESET, "loopback connection reset") from error
        except OSError as error:
            raise NetworkError(NetworkErrorCode.HOST_FAILURE, f"loopback read failed: {error}") from error
        if not data:
            raise NetworkError(NetworkErrorCode.EOF, "loopback peer closed")
        return data

    def write(self, stream: socket.socket, data: bytes, timeout_ms: int) -> int:
        stream.settimeout(timeout_ms / 1000)
        try:
            return stream.send(data)
        except (TimeoutError, BlockingIOError) as error:
            raise NetworkError(NetworkErrorCode.TIMEOUT, "loopback write timed out") from error
        except (BrokenPipeError, ConnectionResetError) as error:
            raise NetworkError(NetworkErrorCode.CONNECTION_RESET, "loopback connection reset") from error
        except OSError as error:
            raise NetworkError(NetworkErrorCode.HOST_FAILURE, f"loopback write failed: {error}") from error

    @staticmethod
    def close(resource: _LoopbackListener | socket.socket) -> None:
        resource.socket.close() if isinstance(resource, _LoopbackListener) else resource.close()

    @staticmethod
    def bound_address(listener: _LoopbackListener) -> NetworkAddress:
        return listener.address
