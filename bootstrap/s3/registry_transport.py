"""Verified HTTPS content-addressed registry transport for M1.86."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import re
from typing import Protocol
from urllib.parse import urlsplit

from .async_core import AsyncErrorCode, AsyncFuture, complete, fail
from .async_futures import MoveOnlyFuture


_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class RegistryTransportErrorCode:
    INVALID_DIGEST = "invalid_digest"
    INVALID_URI = "invalid_uri"
    TLS = "tls"
    NOT_FOUND = "not_found"
    DIGEST_MISMATCH = "digest_mismatch"
    CACHE_LIMIT = "cache_limit"
    TRANSPORT = "transport"


@dataclass(frozen=True, slots=True)
class VerifiedHTTPSBody:
    certificate_verified: bool
    hostname_verified: bool
    body: bytes


class HTTPSRegistryProvider(Protocol):
    def fetch(self, uri: str) -> VerifiedHTTPSBody: ...


class BoundedVerifiedCache:
    def __init__(self, *, max_entries: int = 128, max_bytes: int = 16 * 1024 * 1024) -> None:
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in (max_entries, max_bytes)):
            raise ValueError("cache limits must be positive integers")
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._items: OrderedDict[str, bytes] = OrderedDict()
        self._bytes = 0

    @property
    def total_bytes(self) -> int:
        return self._bytes

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(self._items)

    def get(self, digest: str) -> bytes | None:
        value = self._items.get(digest)
        if value is not None:
            self._items.move_to_end(digest)
        return value

    def put(self, digest: str, body: bytes) -> bool:
        if len(body) > self.max_bytes:
            return False
        previous = self._items.pop(digest, None)
        if previous is not None:
            self._bytes -= len(previous)
        while self._items and (len(self._items) >= self.max_entries or self._bytes + len(body) > self.max_bytes):
            _old_digest, old_body = self._items.popitem(last=False)
            self._bytes -= len(old_body)
        self._items[digest] = body
        self._bytes += len(body)
        return True


@dataclass(frozen=True, slots=True)
class RegistryObject:
    digest: str
    body: bytes
    from_cache: bool


class HTTPSContentAddressedRegistry:
    """Read-only verified object fetcher with bounded cache."""

    def __init__(
        self,
        provider: HTTPSRegistryProvider,
        *,
        authority: str = "registry.fixture",
        cache: BoundedVerifiedCache | None = None,
    ) -> None:
        if not authority or "/" in authority or ":" in authority:
            raise ValueError("registry authority must be a host name")
        self.provider = provider
        self.authority = authority
        self.cache = cache or BoundedVerifiedCache()

    def fetch(self, digest: str) -> MoveOnlyFuture[RegistryObject]:
        def operation():
            if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
                return _failure(RegistryTransportErrorCode.INVALID_DIGEST, "digest is not lowercase SHA-256")
            cached = self.cache.get(digest)
            if cached is not None:
                return complete(RegistryObject(digest, cached, True))
            uri = f"https://{self.authority}/objects/{digest}"
            try:
                result = self.provider.fetch(uri)
            except Exception as error:
                return _failure(RegistryTransportErrorCode.TRANSPORT, type(error).__name__)
            if not isinstance(result, VerifiedHTTPSBody) or not result.certificate_verified or not result.hostname_verified:
                return _failure(RegistryTransportErrorCode.TLS, "certificate and hostname verification are required")
            if not isinstance(result.body, bytes):
                return _failure(RegistryTransportErrorCode.TRANSPORT, "provider body must be bytes")
            actual = hashlib.sha256(result.body).hexdigest()
            if actual != digest:
                return _failure(RegistryTransportErrorCode.DIGEST_MISMATCH, "returned object hash does not match requested digest")
            if not self.cache.put(digest, result.body):
                return _failure(RegistryTransportErrorCode.CACHE_LIMIT, "verified object exceeds cache byte budget")
            return complete(RegistryObject(digest, result.body, False))
        return MoveOnlyFuture(AsyncFuture(lambda _frame: operation()))


class LocalVerifiedHTTPSFixtures:
    """Test-only HTTPS/TLS provider with explicit verification metadata."""

    def __init__(self) -> None:
        self.responses: dict[str, VerifiedHTTPSBody] = {}

    def add(self, uri: str, body: bytes, *, certificate_verified: bool = True, hostname_verified: bool = True) -> None:
        self.responses[uri] = VerifiedHTTPSBody(certificate_verified, hostname_verified, body)

    def fetch(self, uri: str) -> VerifiedHTTPSBody:
        return self.responses[uri]


def _failure(code: str, detail: str):
    return fail(AsyncErrorCode.CALLBACK_FAILURE, "registry_fetch", f"{code}: {detail}")
