"""Bounded HTTP/1.1 client and deterministic fixture transport for M1.85."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import socket
import ssl
from typing import Protocol
from urllib.parse import urlsplit

from .async_core import AsyncErrorCode, AsyncFuture, complete, fail
from .async_futures import MoveOnlyFuture


class HTTPErrorCode(Enum):
    INVALID_URL = "invalid_url"
    UNSUPPORTED_METHOD = "unsupported_method"
    FIXTURE_NOT_FOUND = "fixture_not_found"
    MALFORMED_RESPONSE = "malformed_response"
    HEADER_LIMIT = "header_limit"
    BODY_LIMIT = "body_limit"
    FRAMING = "framing"
    UNSUPPORTED_TRANSFER = "unsupported_transfer"
    TRANSPORT = "transport"
    TLS = "tls"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class HTTPError:
    code: HTTPErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class HTTPLimits:
    max_request_bytes: int = 16 * 1024
    max_header_bytes: int = 8192
    max_header_line_bytes: int = 2048
    max_headers: int = 64
    max_body_bytes: int = 1 << 20
    max_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        integer_values = (
            self.max_request_bytes,
            self.max_header_bytes,
            self.max_header_line_bytes,
            self.max_headers,
            self.max_body_bytes,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in integer_values):
            raise ValueError("HTTP integer limits must be positive")
        if self.max_header_line_bytes > self.max_header_bytes:
            raise ValueError("HTTP header-line limit cannot exceed total header limit")
        if isinstance(self.max_timeout_seconds, bool) or not isinstance(self.max_timeout_seconds, (int, float)) or not 0 < self.max_timeout_seconds <= 300:
            raise ValueError("HTTP timeout limit must be within (0, 300]")


@dataclass(frozen=True, slots=True)
class HTTPResponse:
    version: str
    status: int
    reason: str
    headers: tuple[tuple[str, str], ...]
    body: bytes

    def header(self, name: str) -> str | None:
        lowered = name.lower()
        for key, value in self.headers:
            if key.lower() == lowered:
                return value
        return None


class HTTPTransport(Protocol):
    """Bounded raw HTTP transport boundary used by the protocol client."""

    def request(
        self,
        *,
        scheme: str,
        host: str,
        port: int,
        request: bytes,
        max_response_bytes: int,
        timeout: float,
    ) -> bytes: ...


class SocketHTTPTransport:
    """Real TCP/TLS transport with secure HTTPS defaults and bounded reads."""

    def __init__(self, *, tls_context: ssl.SSLContext | None = None) -> None:
        context = tls_context or ssl.create_default_context()
        if context.verify_mode != ssl.CERT_REQUIRED or context.check_hostname is not True:
            raise ValueError("HTTPS transport requires certificate and hostname verification")
        self._tls_context = context

    def request(
        self,
        *,
        scheme: str,
        host: str,
        port: int,
        request: bytes,
        max_response_bytes: int,
        timeout: float,
    ) -> bytes:
        raw_socket = socket.create_connection((host, port), timeout=timeout)
        channel: socket.socket = raw_socket
        try:
            if scheme == "https":
                channel = self._tls_context.wrap_socket(raw_socket, server_hostname=host)
            elif scheme != "http":
                raise ValueError("unsupported HTTP transport scheme")
            channel.settimeout(timeout)
            channel.sendall(request)
            response = bytearray()
            while True:
                chunk = channel.recv(min(16 * 1024, max_response_bytes + 1 - len(response)))
                if not chunk:
                    break
                response.extend(chunk)
                if len(response) > max_response_bytes:
                    raise ValueError("HTTP response exceeds transport byte budget")
            return bytes(response)
        finally:
            try:
                channel.close()
            finally:
                if channel is not raw_socket:
                    raw_socket.close()


class BoundedHTTPClient:
    """HTTP/1.1 GET/POST client over an injected bounded transport."""

    def __init__(self, transport: HTTPTransport | None = None, *, limits: HTTPLimits | None = None) -> None:
        self.transport = transport or SocketHTTPTransport()
        self.limits = limits or HTTPLimits()

    def get(self, url: str, *, headers: tuple[tuple[str, str], ...] = (), timeout: float = 10.0) -> MoveOnlyFuture[HTTPResponse]:
        return self.request("GET", url, headers=headers, body=b"", timeout=timeout)

    def post(
        self,
        url: str,
        *,
        body: bytes,
        headers: tuple[tuple[str, str], ...] = (),
        timeout: float = 10.0,
    ) -> MoveOnlyFuture[HTTPResponse]:
        return self.request("POST", url, headers=headers, body=body, timeout=timeout)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: tuple[tuple[str, str], ...] = (),
        body: bytes = b"",
        timeout: float = 10.0,
    ) -> MoveOnlyFuture[HTTPResponse]:
        def operation():
            prepared = _prepare_request(method, url, headers, body, timeout, self.limits)
            if isinstance(prepared, HTTPError):
                return _failure(prepared)
            scheme, host, port, request_bytes = prepared
            max_response = self.limits.max_header_bytes + 4 + self.limits.max_body_bytes
            try:
                raw = self.transport.request(
                    scheme=scheme,
                    host=host,
                    port=port,
                    request=request_bytes,
                    max_response_bytes=max_response,
                    timeout=float(timeout),
                )
            except ssl.SSLError as error:
                return _failure(HTTPError(HTTPErrorCode.TLS, "request", type(error).__name__))
            except (TimeoutError, socket.timeout):
                return _failure(HTTPError(HTTPErrorCode.TIMEOUT, "request", "HTTP transport timed out"))
            except (OSError, ValueError) as error:
                return _failure(HTTPError(HTTPErrorCode.TRANSPORT, "request", str(error)))
            response = parse_http_response(raw, self.limits)
            if isinstance(response, HTTPError):
                return _failure(response)
            return complete(response)
        return MoveOnlyFuture(AsyncFuture(lambda _frame: operation()))


class LocalHTTPFixtures:
    """Deterministic raw HTTP response store; never opens a network channel."""

    def __init__(self, *, max_fixtures: int = 128) -> None:
        if isinstance(max_fixtures, bool) or not isinstance(max_fixtures, int) or max_fixtures <= 0:
            raise ValueError("max_fixtures must be a positive integer")
        self._max = max_fixtures
        self._responses: dict[str, bytes] = {}

    def add(self, path: str, response: bytes) -> None:
        if not isinstance(path, str) or not path.startswith("/") or "\x00" in path or not isinstance(response, bytes):
            raise ValueError("fixture path and response are invalid")
        if path not in self._responses and len(self._responses) >= self._max:
            raise ValueError("fixture limit exceeded")
        self._responses[path] = response

    def get(self, path: str) -> bytes | None:
        return self._responses.get(path)


class _FixtureTransport:
    def __init__(self, fixtures: LocalHTTPFixtures) -> None:
        self.fixtures = fixtures

    def request(
        self,
        *,
        scheme: str,
        host: str,
        port: int,
        request: bytes,
        max_response_bytes: int,
        timeout: float,
    ) -> bytes:
        del port, timeout
        if scheme != "http" or host != "fixture.local":
            raise ValueError("fixture transport accepts only http://fixture.local")
        request_line = request.split(b"\r\n", 1)[0]
        parts = request_line.split(b" ")
        if len(parts) != 3:
            raise ValueError("fixture request line is malformed")
        path = parts[1].decode("ascii")
        response = self.fixtures.get(path)
        if response is None:
            raise FileNotFoundError(path)
        if len(response) > max_response_bytes:
            raise ValueError("fixture exceeds response budget")
        return response


class LocalHTTPClient(BoundedHTTPClient):
    """Compatibility fixture client backed by the same bounded HTTP parser."""

    def __init__(self, fixtures: LocalHTTPFixtures, *, limits: HTTPLimits | None = None) -> None:
        self.fixtures = fixtures
        super().__init__(_FixtureTransport(fixtures), limits=limits)

    def get(self, url: str) -> MoveOnlyFuture[HTTPResponse]:
        parsed = urlsplit(url) if isinstance(url, str) else None
        if parsed is None or parsed.scheme != "http" or parsed.netloc != "fixture.local" or parsed.query or parsed.fragment or not parsed.path.startswith("/"):
            return MoveOnlyFuture(AsyncFuture(lambda _frame: _failure(HTTPError(HTTPErrorCode.INVALID_URL, "get", "only http://fixture.local paths are supported"))))
        if self.fixtures.get(parsed.path) is None:
            return MoveOnlyFuture(AsyncFuture(lambda _frame: _failure(HTTPError(HTTPErrorCode.FIXTURE_NOT_FOUND, "get", parsed.path))))
        return super().get(url)


def _prepare_request(
    method: str,
    url: str,
    headers: tuple[tuple[str, str], ...],
    body: bytes,
    timeout: float,
    limits: HTTPLimits,
) -> tuple[str, str, int, bytes] | HTTPError:
    if method not in {"GET", "POST"}:
        return HTTPError(HTTPErrorCode.UNSUPPORTED_METHOD, "request", "only GET and POST are supported")
    if not isinstance(body, bytes) or len(body) > limits.max_body_bytes:
        return HTTPError(HTTPErrorCode.BODY_LIMIT, "request", "request body exceeds byte budget")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= limits.max_timeout_seconds:
        return HTTPError(HTTPErrorCode.TIMEOUT, "request", "timeout exceeds client budget")
    parsed = urlsplit(url) if isinstance(url, str) else None
    if parsed is None or parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.fragment:
        return HTTPError(HTTPErrorCode.INVALID_URL, "request", "URL must be absolute HTTP(S) without credentials or fragment")
    host = parsed.hostname
    if not host or "\x00" in host:
        return HTTPError(HTTPErrorCode.INVALID_URL, "request", "URL host is invalid")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return HTTPError(HTTPErrorCode.INVALID_URL, "request", "URL port is invalid")
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    try:
        path_bytes = path.encode("ascii")
    except UnicodeEncodeError:
        return HTTPError(HTTPErrorCode.INVALID_URL, "request", "request target must be ASCII")
    if b"\r" in path_bytes or b"\n" in path_bytes or b" " in path_bytes:
        return HTTPError(HTTPErrorCode.INVALID_URL, "request", "request target contains unsafe characters")
    if len(headers) > limits.max_headers:
        return HTTPError(HTTPErrorCode.HEADER_LIMIT, "request", "request header count exceeds limit")

    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, value in headers:
        if not _valid_header_name(key) or not isinstance(value, str) or "\r" in value or "\n" in value or "\x00" in value:
            return HTTPError(HTTPErrorCode.MALFORMED_RESPONSE, "request", "request header contains invalid characters")
        lower = key.lower()
        if lower in seen or lower in {"host", "content-length", "connection"}:
            return HTTPError(HTTPErrorCode.FRAMING, "request", "duplicate or reserved framing header")
        seen.add(lower)
        normalized.append((key, value.strip()))

    host_header = host if port in {80, 443} else f"{host}:{port}"
    wire_headers = [("Host", host_header), *normalized, ("Content-Length", str(len(body))), ("Connection", "close")]
    header_lines = [f"{key}: {value}".encode("ascii") for key, value in wire_headers]
    if any(len(line) > limits.max_header_line_bytes for line in header_lines):
        return HTTPError(HTTPErrorCode.HEADER_LIMIT, "request", "request header line exceeds limit")
    header_bytes = b"\r\n".join(header_lines)
    if len(header_bytes) > limits.max_header_bytes:
        return HTTPError(HTTPErrorCode.HEADER_LIMIT, "request", "request headers exceed byte budget")
    request_bytes = method.encode("ascii") + b" " + path_bytes + b" HTTP/1.1\r\n" + header_bytes + b"\r\n\r\n" + body
    if len(request_bytes) > limits.max_request_bytes + limits.max_body_bytes:
        return HTTPError(HTTPErrorCode.BODY_LIMIT, "request", "request exceeds total byte budget")
    return parsed.scheme, host, port, request_bytes


def parse_http_response(raw: bytes, limits: HTTPLimits | None = None) -> HTTPResponse | HTTPError:
    limits = limits or HTTPLimits()
    if not isinstance(raw, bytes):
        return HTTPError(HTTPErrorCode.MALFORMED_RESPONSE, "parse", "response must be bytes")
    separator = b"\r\n\r\n"
    marker = raw.find(separator)
    if marker < 0:
        return HTTPError(HTTPErrorCode.MALFORMED_RESPONSE, "parse", "header terminator is missing")
    header_bytes = raw[:marker]
    body = raw[marker + len(separator):]
    if len(header_bytes) > limits.max_header_bytes:
        return HTTPError(HTTPErrorCode.HEADER_LIMIT, "parse", "response headers exceed byte budget")
    lines = header_bytes.split(b"\r\n")
    if any(len(line) > limits.max_header_line_bytes for line in lines):
        return HTTPError(HTTPErrorCode.HEADER_LIMIT, "parse", "response header line exceeds limit")
    if not lines or len(lines[0].split(b" ", 2)) != 3:
        return HTTPError(HTTPErrorCode.MALFORMED_RESPONSE, "parse", "status line is malformed")
    version_raw, status_raw, reason_raw = lines[0].split(b" ", 2)
    if version_raw != b"HTTP/1.1":
        return HTTPError(HTTPErrorCode.MALFORMED_RESPONSE, "parse", "only HTTP/1.1 is supported")
    try:
        status = int(status_raw)
    except ValueError:
        return HTTPError(HTTPErrorCode.MALFORMED_RESPONSE, "parse", "status is not numeric")
    if not 100 <= status <= 599:
        return HTTPError(HTTPErrorCode.MALFORMED_RESPONSE, "parse", "status is out of range")
    headers: list[tuple[str, str]] = []
    names: set[str] = set()
    for line in lines[1:]:
        if not line or b":" not in line:
            return HTTPError(HTTPErrorCode.MALFORMED_RESPONSE, "parse", "header line is malformed")
        key_raw, value_raw = line.split(b":", 1)
        try:
            key = key_raw.decode("ascii")
            value = value_raw.decode("ascii").strip()
        except UnicodeDecodeError:
            return HTTPError(HTTPErrorCode.MALFORMED_RESPONSE, "parse", "header is not ASCII")
        lowered = key.lower()
        if not _valid_header_name(key) or lowered in names or "\r" in value or "\n" in value:
            return HTTPError(HTTPErrorCode.MALFORMED_RESPONSE, "parse", "duplicate or invalid header")
        names.add(lowered)
        headers.append((key, value))
    if len(headers) > limits.max_headers:
        return HTTPError(HTTPErrorCode.HEADER_LIMIT, "parse", "header count exceeds limit")
    transfer = next((value for key, value in headers if key.lower() == "transfer-encoding"), None)
    if transfer is not None:
        return HTTPError(HTTPErrorCode.UNSUPPORTED_TRANSFER, "parse", "transfer encoding is not supported in V1")
    content_length = next((value for key, value in headers if key.lower() == "content-length"), None)
    if content_length is None:
        return HTTPError(HTTPErrorCode.FRAMING, "parse", "Content-Length is required")
    try:
        expected = int(content_length)
    except ValueError:
        return HTTPError(HTTPErrorCode.FRAMING, "parse", "Content-Length is not numeric")
    if expected < 0 or expected != len(body):
        return HTTPError(HTTPErrorCode.FRAMING, "parse", "Content-Length does not match body")
    if expected > limits.max_body_bytes:
        return HTTPError(HTTPErrorCode.BODY_LIMIT, "parse", "response body exceeds byte budget")
    return HTTPResponse("HTTP/1.1", status, reason_raw.decode("ascii", errors="replace"), tuple(headers), body)


def _valid_header_name(value: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    token = "!#$%&'*+-.^_`|~"
    return all(char.isalnum() or char in token for char in value)


def _failure(error: HTTPError):
    return fail(AsyncErrorCode.CALLBACK_FAILURE, error.operation, f"{error.code.value}: {error.detail}")
