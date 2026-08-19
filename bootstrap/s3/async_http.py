"""Bounded HTTP/1.1 parsing over local fixtures for M1.85."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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


@dataclass(frozen=True, slots=True)
class HTTPError:
    code: HTTPErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class HTTPLimits:
    max_request_bytes: int = 4096
    max_header_bytes: int = 8192
    max_headers: int = 64
    max_body_bytes: int = 1 << 20

    def __post_init__(self) -> None:
        values = (self.max_request_bytes, self.max_header_bytes, self.max_headers, self.max_body_bytes)
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            raise ValueError("HTTP limits must be positive integers")


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


class LocalHTTPFixtures:
    """Deterministic raw HTTP response store; never opens a network channel."""

    def __init__(self, *, max_fixtures: int = 128) -> None:
        if isinstance(max_fixtures, bool) or not isinstance(max_fixtures, int) or max_fixtures <= 0:
            raise ValueError("max_fixtures must be a positive integer")
        self._max = max_fixtures
        self._responses: dict[str, bytes] = {}

    def add(self, path: str, response: bytes) -> None:
        if not path.startswith("/") or "\x00" in path or not isinstance(response, bytes):
            raise ValueError("fixture path and response are invalid")
        if path not in self._responses and len(self._responses) >= self._max:
            raise ValueError("fixture limit exceeded")
        self._responses[path] = response

    def get(self, path: str) -> bytes | None:
        return self._responses.get(path)


class LocalHTTPClient:
    """HTTP/1.1 GET client constrained to the local fixture authority."""

    def __init__(self, fixtures: LocalHTTPFixtures, *, limits: HTTPLimits | None = None) -> None:
        self.fixtures = fixtures
        self.limits = limits or HTTPLimits()

    def get(self, url: str) -> MoveOnlyFuture[HTTPResponse]:
        def operation():
            parsed = urlsplit(url) if isinstance(url, str) else None
            if parsed is None or parsed.scheme != "http" or parsed.netloc != "fixture.local" or parsed.query or parsed.fragment or not parsed.path.startswith("/"):
                return _failure(HTTPError(HTTPErrorCode.INVALID_URL, "get", "only http://fixture.local paths are supported"))
            raw = self.fixtures.get(parsed.path)
            if raw is None:
                return _failure(HTTPError(HTTPErrorCode.FIXTURE_NOT_FOUND, "get", parsed.path))
            if len(raw) > self.limits.max_request_bytes + self.limits.max_header_bytes + self.limits.max_body_bytes:
                return _failure(HTTPError(HTTPErrorCode.BODY_LIMIT, "get", "fixture exceeds total response budget"))
            response = parse_http_response(raw, self.limits)
            if isinstance(response, HTTPError):
                return _failure(response)
            return complete(response)
        return MoveOnlyFuture(AsyncFuture(lambda _frame: operation()))


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
        if b":" not in line:
            return HTTPError(HTTPErrorCode.MALFORMED_RESPONSE, "parse", "header line is malformed")
        key_raw, value_raw = line.split(b":", 1)
        try:
            key = key_raw.decode("ascii")
            value = value_raw.decode("ascii").strip()
        except UnicodeDecodeError:
            return HTTPError(HTTPErrorCode.MALFORMED_RESPONSE, "parse", "header is not ASCII")
        lowered = key.lower()
        if not key or lowered in names:
            return HTTPError(HTTPErrorCode.MALFORMED_RESPONSE, "parse", "duplicate or empty header")
        names.add(lowered)
        headers.append((key, value))
    if len(headers) > limits.max_headers:
        return HTTPError(HTTPErrorCode.HEADER_LIMIT, "parse", "header count exceeds limit")
    transfer = next((value for key, value in headers if key.lower() == "transfer-encoding"), None)
    if transfer is not None:
        return HTTPError(HTTPErrorCode.UNSUPPORTED_TRANSFER, "parse", "chunked transfer is not supported")
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


def _failure(error: HTTPError):
    return fail(AsyncErrorCode.CALLBACK_FAILURE, error.operation, f"{error.code.value}: {error.detail}")
