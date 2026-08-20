"""Bounded incremental HTTP/1.1 server framing for M1.93."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import ipaddress
import socket
import time
from typing import Callable

from .async_http import HTTPLimits
from .results import Result


class HTTPServerErrorCode(Enum):
    INVALID_ARGUMENT = "invalid_argument"
    CLOSED = "closed"
    CONNECTION_LIMIT = "connection_limit"
    HEADER_LIMIT = "header_limit"
    BODY_LIMIT = "body_limit"
    FRAMING = "framing"
    MALFORMED = "malformed"
    UNSUPPORTED_TRANSFER = "unsupported_transfer"
    QUEUE_LIMIT = "queue_limit"
    TIMEOUT = "timeout"
    TRANSPORT = "transport"
    HANDLER = "handler"


@dataclass(frozen=True, slots=True)
class HTTPServerError:
    code: HTTPServerErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class HTTPRequest:
    method: str
    target: str
    version: str
    headers: tuple[tuple[str, str], ...]
    body: bytes

    def header(self, name: str) -> str | None:
        lowered = name.lower()
        for key, value in self.headers:
            if key.lower() == lowered:
                return value
        return None


@dataclass(frozen=True, slots=True)
class HTTPServerResponse:
    status: int
    reason: str
    headers: tuple[tuple[str, str], ...]
    body: bytes = b""

    def encode(self, limits: HTTPLimits | None = None) -> Result[bytes, HTTPServerError]:
        limits = limits or HTTPLimits()
        if isinstance(self.status, bool) or not isinstance(self.status, int) or not 100 <= self.status <= 599:
            return Result.err(HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "response", "status is outside 100..599"))
        if not isinstance(self.reason, str) or not self.reason.isascii() or "\r" in self.reason or "\n" in self.reason:
            return Result.err(HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "response", "reason is not safe ASCII text"))
        if not isinstance(self.body, bytes) or len(self.body) > limits.max_body_bytes:
            return Result.err(HTTPServerError(HTTPServerErrorCode.BODY_LIMIT, "response", "response body exceeds limit"))
        if len(self.headers) > limits.max_headers:
            return Result.err(HTTPServerError(HTTPServerErrorCode.HEADER_LIMIT, "response", "response header count exceeds limit"))
        normalized: list[tuple[str, str]] = []
        names: set[str] = set()
        for key, value in self.headers:
            if not _valid_header_name(key) or not isinstance(value, str) or not value.isascii() or "\r" in value or "\n" in value or "\x00" in value:
                return Result.err(HTTPServerError(HTTPServerErrorCode.MALFORMED, "response", "response header is invalid"))
            lowered = key.lower()
            if lowered in names or lowered in {"content-length", "transfer-encoding", "connection"}:
                return Result.err(HTTPServerError(HTTPServerErrorCode.FRAMING, "response", "duplicate or reserved response framing header"))
            names.add(lowered)
            normalized.append((key, value.strip()))
        lines = [f"HTTP/1.1 {self.status} {self.reason}".encode("ascii")]
        lines.extend(f"{key}: {value}".encode("ascii") for key, value in normalized)
        lines.extend((f"Content-Length: {len(self.body)}".encode("ascii"), b"Connection: close"))
        if any(len(line) > limits.max_header_line_bytes for line in lines):
            return Result.err(HTTPServerError(HTTPServerErrorCode.HEADER_LIMIT, "response", "response header line exceeds limit"))
        header_bytes = b"\r\n".join(lines)
        if len(header_bytes) > limits.max_header_bytes:
            return Result.err(HTTPServerError(HTTPServerErrorCode.HEADER_LIMIT, "response", "response headers exceed limit"))
        return Result.ok(header_bytes + b"\r\n\r\n" + self.body)


class IncrementalHTTPRequestParser:
    """Incremental request parser with bounded frame and body storage."""

    def __init__(self, *, limits: HTTPLimits | None = None, max_frames: int = 8) -> None:
        if isinstance(max_frames, bool) or not isinstance(max_frames, int) or max_frames <= 0:
            raise ValueError("max_frames must be a positive integer")
        self.limits = limits or HTTPLimits()
        self.max_frames = max_frames
        self._buffer = bytearray()
        self._head: tuple[str, str, str, tuple[tuple[str, str], ...], int] | None = None

    def feed(self, data: bytes) -> Result[tuple[HTTPRequest, ...], HTTPServerError]:
        if not isinstance(data, bytes):
            return Result.err(HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "feed", "input must be bytes"))
        if len(self._buffer) + len(data) > self.limits.max_request_bytes + self.limits.max_body_bytes:
            return Result.err(HTTPServerError(HTTPServerErrorCode.BODY_LIMIT, "feed", "request stream exceeds byte budget"))
        self._buffer.extend(data)
        requests: list[HTTPRequest] = []
        while len(requests) < self.max_frames:
            if self._head is None:
                marker = self._buffer.find(b"\r\n\r\n")
                if marker < 0:
                    if len(self._buffer) > self.limits.max_header_bytes:
                        return Result.err(HTTPServerError(HTTPServerErrorCode.HEADER_LIMIT, "feed", "request headers exceed limit"))
                    break
                head_bytes = bytes(self._buffer[:marker])
                del self._buffer[: marker + 4]
                parsed = _parse_request_head(head_bytes, self.limits)
                if isinstance(parsed, HTTPServerError):
                    return Result.err(parsed)
                self._head = parsed
            assert self._head is not None
            method, target, version, headers, length = self._head
            if len(self._buffer) < length:
                break
            body = bytes(self._buffer[:length])
            del self._buffer[:length]
            requests.append(HTTPRequest(method, target, version, headers, body))
            self._head = None
        if self._head is None and self._buffer and len(requests) >= self.max_frames:
            return Result.err(HTTPServerError(HTTPServerErrorCode.QUEUE_LIMIT, "feed", "request frame queue limit exceeded"))
        return Result.ok(tuple(requests))

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer) + (0 if self._head is None else self._head[4])


@dataclass(slots=True)
class _ServerConnection:
    parser: IncrementalHTTPRequestParser
    closed: bool = False


class StreamingHTTPServer:
    """Transport-neutral bounded server session registry."""

    def __init__(self, *, limits: HTTPLimits | None = None, max_connections: int = 32, max_frames: int = 8) -> None:
        if isinstance(max_connections, bool) or not isinstance(max_connections, int) or max_connections <= 0:
            raise ValueError("max_connections must be a positive integer")
        self.limits = limits or HTTPLimits()
        self.max_connections = max_connections
        self.max_frames = max_frames
        self._connections: dict[str, _ServerConnection] = {}

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    def open(self, connection_id: str) -> Result[None, HTTPServerError]:
        if not isinstance(connection_id, str) or not connection_id or "\x00" in connection_id:
            return Result.err(HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "open", "connection id is invalid"))
        if connection_id in self._connections:
            return Result.err(HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "open", "connection is already open"))
        if len(self._connections) >= self.max_connections:
            return Result.err(HTTPServerError(HTTPServerErrorCode.CONNECTION_LIMIT, "open", "connection limit exceeded"))
        self._connections[connection_id] = _ServerConnection(IncrementalHTTPRequestParser(limits=self.limits, max_frames=self.max_frames))
        return Result.ok(None)

    def receive(self, connection_id: str, data: bytes) -> Result[tuple[HTTPRequest, ...], HTTPServerError]:
        connection = self._connections.get(connection_id)
        if connection is None or connection.closed:
            return Result.err(HTTPServerError(HTTPServerErrorCode.CLOSED, "receive", "connection is closed or unknown"))
        return connection.parser.feed(data)

    def close(self, connection_id: str) -> Result[None, HTTPServerError]:
        connection = self._connections.get(connection_id)
        if connection is None:
            return Result.err(HTTPServerError(HTTPServerErrorCode.CLOSED, "close", "connection is unknown"))
        connection.closed = True
        self._connections.pop(connection_id, None)
        return Result.ok(None)


class LoopbackHTTPServer:
    """Bounded real-TCP loopback adapter for the HTTP server protocol."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        limits: HTTPLimits | None = None,
        max_connections: int = 32,
        max_chunk_bytes: int = 4096,
    ) -> None:
        try:
            address = ipaddress.ip_address(host)
        except ValueError as error:
            raise ValueError("loopback HTTP host must be a numeric address") from error
        if not address.is_loopback:
            raise ValueError("loopback HTTP server requires a loopback address")
        if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
            raise ValueError("loopback HTTP port must be in 0..65535")
        if isinstance(max_connections, bool) or not isinstance(max_connections, int) or max_connections <= 0:
            raise ValueError("max_connections must be a positive integer")
        if isinstance(max_chunk_bytes, bool) or not isinstance(max_chunk_bytes, int) or max_chunk_bytes <= 0:
            raise ValueError("max_chunk_bytes must be a positive integer")
        self.host = host
        self.port = port
        self.limits = limits or HTTPLimits()
        self.max_connections = max_connections
        self.max_chunk_bytes = max_chunk_bytes
        self._listener: socket.socket | None = None
        self._address: tuple[str, int] | None = None
        self._active_connections = 0

    @property
    def address(self) -> tuple[str, int] | None:
        return self._address

    @property
    def active_connections(self) -> int:
        return self._active_connections

    def start(self) -> Result[tuple[str, int], HTTPServerError]:
        if self._listener is not None:
            return Result.err(HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "start", "server is already started"))
        family = socket.AF_INET6 if ":" in self.host else socket.AF_INET
        listener = socket.socket(family, socket.SOCK_STREAM)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((self.host, self.port))
            listener.listen(self.max_connections)
            bound = listener.getsockname()
            self._listener = listener
            self._address = (self.host, int(bound[1]))
            return Result.ok(self._address)
        except OSError as error:
            listener.close()
            return Result.err(HTTPServerError(HTTPServerErrorCode.TRANSPORT, "start", f"loopback listen failed: {error}"))

    def serve_once(self, handler: Callable[[HTTPRequest], HTTPServerResponse]) -> Result[None, HTTPServerError]:
        if not callable(handler):
            return Result.err(HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "serve_once", "request handler is not callable"))
        listener = self._listener
        if listener is None:
            return Result.err(HTTPServerError(HTTPServerErrorCode.CLOSED, "serve_once", "server is not started"))
        deadline = time.monotonic() + self.limits.max_timeout_seconds
        try:
            remaining = _remaining_seconds(deadline)
            if remaining <= 0:
                return Result.err(HTTPServerError(HTTPServerErrorCode.TIMEOUT, "accept", "request deadline expired"))
            listener.settimeout(remaining)
            connection, _address = listener.accept()
        except socket.timeout:
            return Result.err(HTTPServerError(HTTPServerErrorCode.TIMEOUT, "accept", "request deadline expired"))
        except OSError as error:
            return Result.err(HTTPServerError(HTTPServerErrorCode.TRANSPORT, "accept", f"loopback accept failed: {error}"))

        self._active_connections += 1
        try:
            with connection:
                parser = IncrementalHTTPRequestParser(limits=self.limits, max_frames=1)
                requests: tuple[HTTPRequest, ...] = ()
                while not requests:
                    remaining = _remaining_seconds(deadline)
                    if remaining <= 0:
                        return Result.err(HTTPServerError(HTTPServerErrorCode.TIMEOUT, "receive", "request deadline expired"))
                    connection.settimeout(remaining)
                    try:
                        chunk = connection.recv(min(self.max_chunk_bytes, self.limits.max_request_bytes + self.limits.max_body_bytes))
                    except socket.timeout:
                        return Result.err(HTTPServerError(HTTPServerErrorCode.TIMEOUT, "receive", "request deadline expired"))
                    except OSError as error:
                        return Result.err(HTTPServerError(HTTPServerErrorCode.TRANSPORT, "receive", f"loopback receive failed: {error}"))
                    if not chunk:
                        return Result.err(HTTPServerError(HTTPServerErrorCode.MALFORMED, "receive", "peer closed before a complete request"))
                    parsed = parser.feed(chunk)
                    if parsed.is_err:
                        return Result.err(parsed.error_or(None))
                    requests = parsed.value_or(())

                try:
                    response = handler(requests[0])
                except Exception as error:
                    return Result.err(HTTPServerError(HTTPServerErrorCode.HANDLER, "handler", f"request handler failed: {error}"))
                if not isinstance(response, HTTPServerResponse):
                    return Result.err(HTTPServerError(HTTPServerErrorCode.HANDLER, "handler", "request handler returned an invalid response"))
                encoded = response.encode(self.limits)
                if encoded.is_err:
                    return Result.err(encoded.error_or(None))
                payload = encoded.value_or(b"")
                offset = 0
                while offset < len(payload):
                    remaining = _remaining_seconds(deadline)
                    if remaining <= 0:
                        return Result.err(HTTPServerError(HTTPServerErrorCode.TIMEOUT, "send", "response deadline expired"))
                    connection.settimeout(remaining)
                    try:
                        sent = connection.send(payload[offset : offset + self.max_chunk_bytes])
                    except socket.timeout:
                        return Result.err(HTTPServerError(HTTPServerErrorCode.TIMEOUT, "send", "response deadline expired"))
                    except OSError as error:
                        return Result.err(HTTPServerError(HTTPServerErrorCode.TRANSPORT, "send", f"loopback send failed: {error}"))
                    if sent <= 0:
                        return Result.err(HTTPServerError(HTTPServerErrorCode.TRANSPORT, "send", "loopback send made no progress"))
                    offset += sent
                return Result.ok(None)
        finally:
            self._active_connections -= 1

    def close(self) -> Result[None, HTTPServerError]:
        listener = self._listener
        self._listener = None
        self._address = None
        if listener is None:
            return Result.ok(None)
        try:
            listener.close()
        except OSError as error:
            return Result.err(HTTPServerError(HTTPServerErrorCode.TRANSPORT, "close", f"loopback close failed: {error}"))
        return Result.ok(None)


def _parse_request_head(
    raw: bytes,
    limits: HTTPLimits,
) -> tuple[str, str, str, tuple[tuple[str, str], ...], int] | HTTPServerError:
    if len(raw) > limits.max_header_bytes:
        return HTTPServerError(HTTPServerErrorCode.HEADER_LIMIT, "parse", "request headers exceed limit")
    lines = raw.split(b"\r\n")
    if not lines or len(lines[0].split(b" ")) != 3:
        return HTTPServerError(HTTPServerErrorCode.MALFORMED, "parse", "request line is malformed")
    method_raw, target_raw, version_raw = lines[0].split(b" ")
    if not method_raw or not all(chr(item).isalpha() for item in method_raw):
        return HTTPServerError(HTTPServerErrorCode.MALFORMED, "parse", "request method is invalid")
    if version_raw != b"HTTP/1.1" or not target_raw or b"\r" in target_raw or b"\n" in target_raw:
        return HTTPServerError(HTTPServerErrorCode.MALFORMED, "parse", "request target or version is invalid")
    try:
        method = method_raw.decode("ascii")
        target = target_raw.decode("ascii")
    except UnicodeDecodeError:
        return HTTPServerError(HTTPServerErrorCode.MALFORMED, "parse", "request line must be ASCII")
    headers: list[tuple[str, str]] = []
    content_lengths: list[str] = []
    for line in lines[1:]:
        if not line or b":" not in line:
            return HTTPServerError(HTTPServerErrorCode.MALFORMED, "parse", "header line is malformed")
        key_raw, value_raw = line.split(b":", 1)
        try:
            key = key_raw.decode("ascii")
            value = value_raw.decode("ascii").strip()
        except UnicodeDecodeError:
            return HTTPServerError(HTTPServerErrorCode.MALFORMED, "parse", "header is not ASCII")
        if not _valid_header_name(key) or "\r" in value or "\n" in value or "\x00" in value:
            return HTTPServerError(HTTPServerErrorCode.MALFORMED, "parse", "header contains unsafe characters")
        if len(line) > limits.max_header_line_bytes:
            return HTTPServerError(HTTPServerErrorCode.HEADER_LIMIT, "parse", "header line exceeds limit")
        lowered = key.lower()
        if lowered == "transfer-encoding":
            return HTTPServerError(HTTPServerErrorCode.UNSUPPORTED_TRANSFER, "parse", "transfer encoding is not accepted")
        if lowered == "content-length":
            content_lengths.append(value)
        headers.append((key, value))
    if len(headers) > limits.max_headers:
        return HTTPServerError(HTTPServerErrorCode.HEADER_LIMIT, "parse", "header count exceeds limit")
    if len(content_lengths) > 1 or any(not value.isdigit() for value in content_lengths):
        return HTTPServerError(HTTPServerErrorCode.FRAMING, "parse", "content length is duplicated or invalid")
    length = int(content_lengths[0]) if content_lengths else 0
    if length > limits.max_body_bytes:
        return HTTPServerError(HTTPServerErrorCode.BODY_LIMIT, "parse", "request body exceeds limit")
    return method, target, "HTTP/1.1", tuple(headers), length


def _valid_header_name(name: str) -> bool:
    return bool(name) and all(character.isalnum() or character == "-" for character in name)


def _remaining_seconds(deadline: float) -> float:
    return deadline - time.monotonic()
