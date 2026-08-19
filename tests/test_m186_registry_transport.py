from __future__ import annotations

import hashlib

from bootstrap.s3.registry_transport import (
    BoundedVerifiedCache,
    HTTPSContentAddressedRegistry,
    LocalVerifiedHTTPSFixtures,
)


def test_https_registry_verifies_digest_and_caches_only_verified_bytes() -> None:
    body = b"package-object"
    digest = hashlib.sha256(body).hexdigest()
    provider = LocalVerifiedHTTPSFixtures()
    provider.add(f"https://registry.fixture/objects/{digest}", body)
    registry = HTTPSContentAddressedRegistry(provider, cache=BoundedVerifiedCache(max_entries=2, max_bytes=64))
    first = registry.fetch(digest).await_once().value_or(None)
    assert first.body == body and first.from_cache is False
    provider.responses.clear()
    second = registry.fetch(digest).await_once().value_or(None)
    assert second.body == body and second.from_cache is True


def test_registry_rejects_tls_failures_and_digest_mismatches() -> None:
    body = b"signed-later"
    digest = hashlib.sha256(body).hexdigest()
    provider = LocalVerifiedHTTPSFixtures()
    provider.add(f"https://registry.fixture/objects/{digest}", body, hostname_verified=False)
    registry = HTTPSContentAddressedRegistry(provider)
    tls_failure = registry.fetch(digest).poll().value_or(None)
    assert tls_failure.error is not None and "tls" in tls_failure.error.detail
    provider.responses.clear()
    provider.add(f"https://registry.fixture/objects/{digest}", b"wrong")
    mismatch = registry.fetch(digest).poll().value_or(None)
    assert mismatch.error is not None and "digest_mismatch" in mismatch.error.detail


def test_cache_is_bounded_and_evicts_deterministically() -> None:
    cache = BoundedVerifiedCache(max_entries=2, max_bytes=10)
    assert cache.put("a" * 64, b"1234")
    assert cache.put("b" * 64, b"5678")
    assert cache.put("c" * 64, b"90")
    assert cache.keys == ("b" * 64, "c" * 64)
    assert cache.total_bytes == 6
