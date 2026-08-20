"""Verified HTTPS content-addressed registry transport for M1.86."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import re

from .async_core import AsyncErrorCode, AsyncFuture, complete, fail
from .async_futures import MoveOnlyFuture
from .async_http import BoundedHTTPClient


_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class RegistryTransportErrorCode:
    INVALID_DIGEST = "invalid_digest"
    INVALID_URI = "invalid_uri"
    HTTP = "http"
    NOT_FOUND = "not_found"
    DIGEST_MISMATCH = "digest_mismatch"
    CACHE_LIMIT = "cache_limit"
    TRANSPORT = "transport"


@dataclass(frozen=True, slots=True)
class RegistryOrigin:
    authority: str

    def __post_init__(self) -> None:
        if not isinstance(self.authority, str) or not self.authority:
            raise ValueError("registry authority must be a canonical host name")
        try:
            self.authority.encode("ascii")
        except UnicodeEncodeError as error:
            raise ValueError("registry authority must be ASCII in V1") from error
        canonical = self.authority.lower()
        if canonical.endswith(".") or len(canonical) > 253:
            raise ValueError("registry authority must be a canonical host name")
        labels = canonical.split(".")
        if not labels or any(_HOST_LABEL.fullmatch(label) is None for label in labels):
            raise ValueError("registry authority must be a canonical host name")
        object.__setattr__(self, "authority", canonical)

    @property
    def base_uri(self) -> str:
        return f"https://{self.authority}"


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
        if len(self._items) >= self.max_entries or self._bytes + len(body) > self.max_bytes:
            return False
        self._items[digest] = body
        self._bytes += len(body)
        return True


@dataclass(frozen=True, slots=True)
class RegistryObject:
    origin: RegistryOrigin
    digest: str
    body: bytes
    from_cache: bool

    @property
    def immutable_identity(self) -> str:
        return f"{self.origin.base_uri}/objects/{self.digest}"


class HTTPSContentAddressedRegistry:
    """Read-only registry object fetcher using the real bounded HTTP/TLS client."""

    def __init__(
        self,
        client: BoundedHTTPClient | None = None,
        *,
        authority: str = "registry.fixture",
        cache: BoundedVerifiedCache | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.client = client or BoundedHTTPClient()
        self.origin = RegistryOrigin(authority)
        self.cache = cache or BoundedVerifiedCache()
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("registry timeout must be positive")
        self.timeout = float(timeout)

    def fetch(self, digest: str) -> MoveOnlyFuture[RegistryObject]:
        def operation():
            if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
                return _failure(RegistryTransportErrorCode.INVALID_DIGEST, "digest is not lowercase SHA-256")
            cached = self.cache.get(digest)
            if cached is not None:
                return complete(RegistryObject(self.origin, digest, cached, True))
            uri = f"{self.origin.base_uri}/objects/{digest}"
            response_result = self.client.get(uri, timeout=self.timeout).await_once(max_polls=4)
            if response_result.is_err:
                error = response_result.error_or(None)
                return _failure(RegistryTransportErrorCode.TRANSPORT, error.detail)
            response = response_result.value_or(None)
            if response.status == 404:
                return _failure(RegistryTransportErrorCode.NOT_FOUND, uri)
            if response.status != 200:
                return _failure(RegistryTransportErrorCode.HTTP, f"registry returned HTTP {response.status}")
            actual = hashlib.sha256(response.body).hexdigest()
            if actual != digest:
                return _failure(RegistryTransportErrorCode.DIGEST_MISMATCH, "returned object hash does not match requested digest")
            if not self.cache.put(digest, response.body):
                return _failure(RegistryTransportErrorCode.CACHE_LIMIT, "verified object exceeds cache byte budget")
            return complete(RegistryObject(self.origin, digest, response.body, False))
        return MoveOnlyFuture(AsyncFuture(lambda _frame: operation()))

    def publish(self, _body: bytes) -> None:
        raise RuntimeError("M1.86 registry transport is read-only; publishing is disabled")


def _failure(code: str, detail: str):
    return fail(AsyncErrorCode.CALLBACK_FAILURE, "registry_fetch", f"{code}: {detail}")
