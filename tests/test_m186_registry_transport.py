from __future__ import annotations

import hashlib

from bootstrap.s3.async_http import BoundedHTTPClient
from bootstrap.s3.registry_transport import BoundedVerifiedCache, HTTPSContentAddressedRegistry


class HTTPSFixtureTransport:
    def __init__(self) -> None:
        self.responses: dict[tuple[str, str, int, bytes], bytes] = {}
        self.calls = []

    def add(self, host: str, path: str, response: bytes) -> None:
        self.responses[("https", host, 443, path.encode("ascii"))] = response

    def request(self, *, scheme, host, port, request, max_response_bytes, timeout):
        self.calls.append((scheme, host, port, request, max_response_bytes, timeout))
        assert scheme == "https"
        request_line = request.split(b"\r\n", 1)[0]
        path = request_line.split(b" ")[1]
        raw = self.responses[(scheme, host, port, path)]
        assert len(raw) <= max_response_bytes
        return raw


def _response(body: bytes, status: int = 200, reason: str = "OK") -> bytes:
    return f"HTTP/1.1 {status} {reason}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("ascii") + body


def test_https_registry_verifies_digest_and_caches_only_verified_bytes() -> None:
    body = b"package-object"
    digest = hashlib.sha256(body).hexdigest()
    transport = HTTPSFixtureTransport()
    transport.add("registry.fixture", f"/objects/{digest}", _response(body))
    registry = HTTPSContentAddressedRegistry(
        BoundedHTTPClient(transport),
        cache=BoundedVerifiedCache(max_entries=2, max_bytes=64),
    )
    first = registry.fetch(digest).await_once().value_or(None)
    assert first.body == body and first.from_cache is False
    assert first.immutable_identity == f"https://registry.fixture/objects/{digest}"
    transport.responses.clear()
    second = registry.fetch(digest).await_once().value_or(None)
    assert second.body == body and second.from_cache is True
    assert len(transport.calls) == 1


def test_registry_rejects_digest_mismatches_and_non_success_status() -> None:
    body = b"signed-later"
    digest = hashlib.sha256(body).hexdigest()
    transport = HTTPSFixtureTransport()
    transport.add("registry.fixture", f"/objects/{digest}", _response(b"wrong"))
    registry = HTTPSContentAddressedRegistry(BoundedHTTPClient(transport))
    mismatch = registry.fetch(digest).poll().value_or(None)
    assert mismatch.error is not None and "digest_mismatch" in mismatch.error.detail

    transport = HTTPSFixtureTransport()
    transport.add("registry.fixture", f"/objects/{digest}", _response(b"", 404, "Not Found"))
    missing = HTTPSContentAddressedRegistry(BoundedHTTPClient(transport)).fetch(digest).poll().value_or(None)
    assert missing.error is not None and "not_found" in missing.error.detail


def test_registry_transport_is_https_only_and_cache_is_bounded() -> None:
    body = b"x"
    digest = hashlib.sha256(body).hexdigest()
    transport = HTTPSFixtureTransport()
    transport.add("registry.fixture", f"/objects/{digest}", _response(body))
    registry = HTTPSContentAddressedRegistry(BoundedHTTPClient(transport))
    assert registry.fetch(digest).await_once().is_ok
    assert transport.calls[0][0] == "https"

    cache = BoundedVerifiedCache(max_entries=2, max_bytes=10)
    assert cache.put("a" * 64, b"1234")
    assert cache.put("b" * 64, b"5678")
    assert cache.put("c" * 64, b"90")
    assert cache.keys == ("b" * 64, "c" * 64)
    assert cache.total_bytes == 6


def test_registry_publishing_remains_disabled() -> None:
    registry = HTTPSContentAddressedRegistry(BoundedHTTPClient(HTTPSFixtureTransport()))
    try:
        registry.publish(b"no")
    except RuntimeError as error:
        assert "disabled" in str(error)
    else:
        raise AssertionError("registry publishing must stay disabled")
