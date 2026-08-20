"""Bounded incremental HTTP/1.1 server framing for M1.93."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import ipaddress
import socket
import time
from collections.abc import Iterable, Iterator
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
    BODY_PENDING = "body_pending"


@dataclass(frozen=True, slots=True)
class HTTPServerError:
    code: HTTPServerErrorCode
    operation: str
    detail: str


class HTTPBodyStreamError(RuntimeError):
    def __init__(self, error: HTTPServerError) -> None:
        super().__init__(error.detail)
        self.error = error


class HTTPBodyReader:
    """Bounded pull-driven Content-Length body reader."""

    def __init__(
        self,
        content_length: int,
        limits: HTTPLimits,
        pull: Callable[[int], Result[bytes | None, HTTPServerError]] | None = None,
    ) -> None:
        self._content_length = content_length
        self._limits = limits
        self._pull = pull
        self._buffer = bytearray()
        self._received = 0
        self._consumed = 0
        self._ended = content_length == 0

    @property
    def content_length(self) -> int:
        return self._content_length

    @property
    def body_bytes_received(self) -> int:
        return self._received

    @property
    def body_bytes_consumed(self) -> int:
        return self._consumed

    @property
    def body_complete(self) -> bool:
        return self._received == self._content_length

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def feed_bytes(self, data: bytes) -> Result[None, HTTPServerError]:
        if not isinstance(data, bytes):
            return Result.err(HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "body", "body input must be bytes"))
        if self.body_complete and data:
            return Result.err(HTTPServerError(HTTPServerErrorCode.FRAMING, "body", "body received bytes after Content-Length completion"))
        remaining = self._content_length - self._received
        if len(data) > remaining:
            return Result.err(HTTPServerError(HTTPServerErrorCode.FRAMING, "body", "body exceeds Content-Length"))
        if len(self._buffer) + len(data) > self._limits.max_buffered_body_bytes:
            return Result.err(HTTPServerError(HTTPServerErrorCode.QUEUE_LIMIT, "body", "body buffer window exceeded; consumer backpressure required"))
        self._buffer.extend(data)
        self._received += len(data)
        return Result.ok(None)

    def read_chunk(self, max_bytes: int | None = None) -> Result[bytes | None, HTTPServerError]:
        limit = max_bytes or self._limits.max_buffered_body_bytes
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            return Result.err(HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "body", "body read size must be positive"))
        if self._buffer:
            size = min(limit, len(self._buffer))
            chunk = bytes(self._buffer[:size])
            del self._buffer[:size]
            self._consumed += len(chunk)
            return Result.ok(chunk)
        if self.body_complete:
            self._ended = True
            return Result.ok(None)
        if self._pull is None:
            return Result.err(HTTPServerError(HTTPServerErrorCode.BODY_PENDING, "body", "body needs more transport data"))
        pulled = self._pull(min(limit, self._limits.max_buffered_body_bytes))
        if pulled.is_err:
            return Result.err(pulled.error_or(None))
        data = pulled.value_or(None)
        if data is None or not data:
            return Result.err(HTTPServerError(HTTPServerErrorCode.MALFORMED, "body", "peer closed before Content-Length body completion"))
        fed = self.feed_bytes(data)
        if fed.is_err:
            return Result.err(fed.error_or(None))
        return self.read_chunk(limit)

    def read_all(self) -> Result[bytes, HTTPServerError]:
        chunks: list[bytes] = []
        while True:
            result = self.read_chunk()
            if result.is_err:
                return Result.err(result.error_or(None))
            chunk = result.value_or(None)
            if chunk is None:
                return Result.ok(b"".join(chunks))
            chunks.append(chunk)

    def __iter__(self) -> Iterator[bytes]:
        while True:
            result = self.read_chunk()
            if result.is_err:
                raise HTTPBodyStreamError(result.error_or(None))
            chunk = result.value_or(None)
            if chunk is None:
                return
            yield chunk


@dataclass(frozen=True, slots=True)
class HTTPRequest:
    method: str
    target: str
    version: str
    headers: tuple[tuple[str, str], ...]
    body_reader: HTTPBodyReader | None = None

    @property
    def body(self) -> bytes:
        """Compatibility view that drains the bounded reader on demand."""
        if self.body_reader is None:
            return b""
        result = self.body_reader.read_all()
        if result.is_err:
            raise HTTPBodyStreamError(result.error_or(None))
        return result.value_or(b"")

    @property
    def body_chunks(self) -> tuple[bytes, ...]:
        if self.body_reader is None:
            return ()
        return tuple(self.body_reader)

    @property
    def body_bytes_received(self) -> int:
        return 0 if self.body_reader is None else self.body_reader.body_bytes_received

    @property
    def body_complete(self) -> bool:
        return self.body_reader is None or self.body_reader.body_complete

    def iter_body(self) -> Iterator[bytes]:
        return iter(self.body_reader or ())

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
    body: bytes | Iterable[bytes] = b""
    content_length: int | None = None

    def encode(self, limits: HTTPLimits | None = None) -> Result[bytes, HTTPServerError]:
        if not isinstance(self.body, bytes):
            return Result.err(HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "response", "streaming body requires open_stream"))
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

    def open_stream(self, limits: HTTPLimits | None = None) -> Result[_HTTPResponseStream, HTTPServerError]:
        limits = limits or HTTPLimits()
        effective_length = len(self.body) if isinstance(self.body, bytes) and self.content_length is None else self.content_length
        checked = _response_header(self.status, self.reason, self.headers, effective_length, limits)
        if isinstance(checked, HTTPServerError):
            return Result.err(checked)
        if isinstance(self.body, bytes):
            source: Iterable[bytes] = () if not self.body else (self.body,)
        elif callable(self.body):
            try:
                source = self.body()
            except Exception as error:
                return Result.err(HTTPServerError(HTTPServerErrorCode.HANDLER, "response", f"response body factory failed: {error}"))
        else:
            source = self.body
        try:
            iterator = iter(source)
        except TypeError:
            return Result.err(HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "response", "streaming body is not iterable"))
        return Result.ok(_HTTPResponseStream(checked, iterator, limits, effective_length))


class _HTTPResponseStream:
    def __init__(self, header: bytes, body: Iterator[bytes], limits: HTTPLimits, content_length: int | None) -> None:
        self._header = header
        self._body = body
        self._limits = limits
        self._content_length = content_length
        self._sent_header = False
        self._body_bytes = 0
        self._closed = False

    def next_chunk(self) -> Result[bytes | None, HTTPServerError]:
        if self._closed:
            return Result.ok(None)
        if not self._sent_header:
            self._sent_header = True
            return Result.ok(self._header)
        try:
            chunk = next(self._body)
        except StopIteration:
            self._closed = True
            if self._content_length is not None and self._body_bytes != self._content_length:
                return Result.err(HTTPServerError(HTTPServerErrorCode.FRAMING, "response", "stream body length does not match Content-Length"))
            return Result.ok(None)
        except Exception as error:
            self._closed = True
            return Result.err(HTTPServerError(HTTPServerErrorCode.HANDLER, "response", f"stream body failed: {error}"))
        if not isinstance(chunk, bytes) or not chunk:
            self._closed = True
            return Result.err(HTTPServerError(HTTPServerErrorCode.MALFORMED, "response", "stream body chunks must be non-empty bytes"))
        self._body_bytes += len(chunk)
        if self._body_bytes > self._limits.max_body_bytes:
            self._closed = True
            return Result.err(HTTPServerError(HTTPServerErrorCode.BODY_LIMIT, "response", "stream response body exceeds limit"))
        if self._content_length is not None and self._body_bytes > self._content_length:
            self._closed = True
            return Result.err(HTTPServerError(HTTPServerErrorCode.FRAMING, "response", "stream body exceeds Content-Length"))
        return Result.ok(chunk)


def _response_header(
    status: int,
    reason: str,
    headers: tuple[tuple[str, str], ...],
    content_length: int | None,
    limits: HTTPLimits,
) -> bytes | HTTPServerError:
    if isinstance(status, bool) or not isinstance(status, int) or not 100 <= status <= 599:
        return HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "response", "status is outside 100..599")
    if not isinstance(reason, str) or not reason.isascii() or "\r" in reason or "\n" in reason:
        return HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "response", "reason is not safe ASCII text")
    if content_length is not None and (isinstance(content_length, bool) or not isinstance(content_length, int) or not 0 <= content_length <= limits.max_body_bytes):
        return HTTPServerError(HTTPServerErrorCode.BODY_LIMIT, "response", "content length is outside the body budget")
    if len(headers) > limits.max_headers:
        return HTTPServerError(HTTPServerErrorCode.HEADER_LIMIT, "response", "response header count exceeds limit")
    normalized: list[tuple[str, str]] = []
    names: set[str] = set()
    for key, value in headers:
        if not _valid_header_name(key) or not isinstance(value, str) or not value.isascii() or "\r" in value or "\n" in value or "\x00" in value:
            return HTTPServerError(HTTPServerErrorCode.MALFORMED, "response", "response header is invalid")
        lowered = key.lower()
        if lowered in names or lowered in {"content-length", "transfer-encoding", "connection"}:
            return HTTPServerError(HTTPServerErrorCode.FRAMING, "response", "duplicate or reserved response framing header")
        names.add(lowered)
        normalized.append((key, value.strip()))
    lines = [f"HTTP/1.1 {status} {reason}".encode("ascii")]
    lines.extend(f"{key}: {value}".encode("ascii") for key, value in normalized)
    if content_length is not None:
        lines.append(f"Content-Length: {content_length}".encode("ascii"))
    lines.append(b"Connection: close")
    if any(len(line) > limits.max_header_line_bytes for line in lines):
        return HTTPServerError(HTTPServerErrorCode.HEADER_LIMIT, "response", "response header line exceeds limit")
    header_bytes = b"\r\n".join(lines) + b"\r\n\r\n"
    if len(header_bytes) > limits.max_header_bytes:
        return HTTPServerError(HTTPServerErrorCode.HEADER_LIMIT, "response", "response headers exceed limit")
    return header_bytes


class IncrementalHTTPRequestParser:
    """Incremental request parser with bounded frame and body storage."""

    def __init__(self, *, limits: HTTPLimits | None = None, max_frames: int = 8) -> None:
        if isinstance(max_frames, bool) or not isinstance(max_frames, int) or max_frames <= 0:
            raise ValueError("max_frames must be a positive integer")
        self.limits = limits or HTTPLimits()
        self.max_frames = max_frames
        self._buffer = bytearray()
        self._head: tuple[str, str, str, tuple[tuple[str, str], ...], int] | None = None
        self._request: HTTPRequest | None = None
        self._body_reader: HTTPBodyReader | None = None
        self._body_puller: Callable[[int], Result[bytes | None, HTTPServerError]] | None = None

    def set_body_puller(self, pull: Callable[[int], Result[bytes | None, HTTPServerError]]) -> None:
        if not callable(pull):
            raise TypeError("body puller must be callable")
        self._body_puller = pull

    def feed(self, data: bytes) -> Result[tuple[HTTPRequest, ...], HTTPServerError]:
        if not isinstance(data, bytes):
            return Result.err(HTTPServerError(HTTPServerErrorCode.INVALID_ARGUMENT, "feed", "input must be bytes"))
        if self._request is not None:
            fed = self._body_reader.feed_bytes(data) if self._body_reader is not None else Result.ok(None)
            if fed.is_err:
                return Result.err(fed.error_or(None))
            return Result.ok(())
        if len(self._buffer) + len(data) > self.limits.max_request_bytes + self.limits.max_body_bytes:
            return Result.err(HTTPServerError(HTTPServerErrorCode.BODY_LIMIT, "feed", "request stream exceeds byte budget"))
        self._buffer.extend(data)
        marker = self._buffer.find(b"\r\n\r\n")
        if marker < 0:
            if len(self._buffer) > self.limits.max_header_bytes:
                return Result.err(HTTPServerError(HTTPServerErrorCode.HEADER_LIMIT, "feed", "request headers exceed limit"))
            return Result.ok(())
        head_bytes = bytes(self._buffer[:marker])
        del self._buffer[: marker + 4]
        parsed = _parse_request_head(head_bytes, self.limits)
        if isinstance(parsed, HTTPServerError):
            return Result.err(parsed)
        self._head = parsed
        method, target, version, headers, length = parsed
        self._body_reader = HTTPBodyReader(length, self.limits, self._body_puller)
        self._request = HTTPRequest(method, target, version, headers, self._body_reader)
        if self._buffer:
            fed = self._body_reader.feed_bytes(bytes(self._buffer))
            self._buffer.clear()
            if fed.is_err:
                return Result.err(fed.error_or(None))
        return Result.ok((self._request,))

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer) + (0 if self._body_reader is None else self._body_reader.buffered_bytes)

    @property
    def body_bytes_received(self) -> int:
        return 0 if self._body_reader is None else self._body_reader.body_bytes_received

    @property
    def body_complete(self) -> bool:
        return self._body_reader is None or self._body_reader.body_complete

    @property
    def body_chunks(self) -> tuple[bytes, ...]:
        return () if self._body_reader is None else tuple(self._body_reader)

    @property
    def body_reader(self) -> HTTPBodyReader | None:
        return self._body_reader


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
        self._accepting = False

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
        if self._active_connections >= self.max_connections or self._accepting:
            return Result.err(HTTPServerError(HTTPServerErrorCode.CONNECTION_LIMIT, "accept", "live connection limit exceeded"))
        deadline = time.monotonic() + self.limits.max_timeout_seconds
        self._accepting = True
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
        finally:
            self._accepting = False

        self._active_connections += 1
        try:
            with connection:
                parser = IncrementalHTTPRequestParser(limits=self.limits, max_frames=1)
                def pull_body(amount: int) -> Result[bytes | None, HTTPServerError]:
                    remaining = _remaining_seconds(deadline)
                    if remaining <= 0:
                        return Result.err(HTTPServerError(HTTPServerErrorCode.TIMEOUT, "receive", "request deadline expired"))
                    connection.settimeout(remaining)
                    try:
                        chunk = connection.recv(amount)
                    except socket.timeout:
                        return Result.err(HTTPServerError(HTTPServerErrorCode.TIMEOUT, "receive", "request deadline expired"))
                    except OSError as error:
                        return Result.err(HTTPServerError(HTTPServerErrorCode.TRANSPORT, "receive", f"loopback receive failed: {error}"))
                    if not chunk:
                        return Result.ok(None)
                    return Result.ok(chunk)

                parser.set_body_puller(pull_body)
                requests: tuple[HTTPRequest, ...] = ()
                while not requests:
                    remaining = _remaining_seconds(deadline)
                    if remaining <= 0:
                        return Result.err(HTTPServerError(HTTPServerErrorCode.TIMEOUT, "receive", "request deadline expired"))
                    connection.settimeout(remaining)
                    try:
                        chunk = connection.recv(
                            min(
                                self.max_chunk_bytes,
                                self.limits.max_header_bytes + self.limits.max_buffered_body_bytes,
                            )
                        )
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
                except HTTPBodyStreamError as error:
                    return Result.err(error.error)
                except Exception as error:
                    return Result.err(HTTPServerError(HTTPServerErrorCode.HANDLER, "handler", f"request handler failed: {error}"))
                if not isinstance(response, HTTPServerResponse):
                    return Result.err(HTTPServerError(HTTPServerErrorCode.HANDLER, "handler", "request handler returned an invalid response"))
                stream = response.open_stream(self.limits)
                if stream.is_err:
                    return Result.err(stream.error_or(None))
                encoder = stream.value_or(None)
                while True:
                    next_chunk = encoder.next_chunk()
                    if next_chunk.is_err:
                        return Result.err(next_chunk.error_or(None))
                    payload = next_chunk.value_or(None)
                    if payload is None:
                        break
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
    if not method_raw or not _valid_token_bytes(method_raw):
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
    token = "!#$%&'*+-.^_`|~"
    return bool(name) and name.isascii() and all(
        ("A" <= character <= "Z")
        or ("a" <= character <= "z")
        or ("0" <= character <= "9")
        or character in token
        for character in name
    )


def _valid_token_bytes(value: bytes) -> bool:
    token = b"!#$%&'*+-.^_`|~"
    return all(65 <= byte <= 90 or 97 <= byte <= 122 or 48 <= byte <= 57 or byte in token for byte in value)


def _remaining_seconds(deadline: float) -> float:
    return deadline - time.monotonic()
