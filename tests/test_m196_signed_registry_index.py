from __future__ import annotations

import hashlib
import json

from bootstrap.s3.package_signatures import PublicTrustStore, TrustedPublicKey
from bootstrap.s3.signed_registry_index import (
    SignedIndexEnvelope,
    SignedIndexErrorCode,
    SignedRegistryIndexTrust,
    canonical_signed_index_payload,
)


class FixtureVerifier:
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        return hashlib.sha256(public_key + message).digest() == signature


def _envelope(generation: int = 1, *, key_id: str = "key-1") -> SignedIndexEnvelope:
    index = json.dumps({
        "format": "s3.registry.index.v2",
        "origin": "https://registry.fixture",
        "packages": [],
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    unsigned = SignedIndexEnvelope("https://registry.fixture", "s3-team", key_id, generation, index, b"placeholder")
    signature = hashlib.sha256(b"public" + canonical_signed_index_payload(unsigned)).digest()
    return SignedIndexEnvelope(unsigned.origin, unsigned.publisher, unsigned.key_id, unsigned.generation, unsigned.index, signature)


def _trust() -> SignedRegistryIndexTrust:
    store = PublicTrustStore()
    assert store.add(TrustedPublicKey("key-1", "s3-team", b"public")).is_ok
    return SignedRegistryIndexTrust(store, FixtureVerifier(), expected_origin="https://registry.fixture")


def test_signed_index_accepts_canonical_trusted_generation() -> None:
    trust = _trust()
    result = trust.verify(_envelope())
    assert result.is_ok
    assert trust.highest_generation == 1
    assert result.value_or(None).document["format"] == "s3.registry.index.v2"


def test_signed_index_rejects_downgrade_rotation_and_revocation() -> None:
    trust = _trust()
    assert trust.verify(_envelope(2)).is_ok
    assert trust.verify(_envelope(1)).error_or(None).code is SignedIndexErrorCode.DOWNGRADE
    assert trust.revoke("key-1").is_ok
    assert trust.verify(_envelope(3)).error_or(None).code is SignedIndexErrorCode.REVOKED_KEY


def test_signed_index_rejects_origin_tampering_and_provider_failure() -> None:
    trust = _trust()
    original = _envelope()
    changed = SignedIndexEnvelope("https://other.fixture", original.publisher, original.key_id, original.generation, original.index, original.signature)
    assert trust.verify(changed).error_or(None).code is SignedIndexErrorCode.INVALID_ENVELOPE

    class MissingProvider:
        def verify(self, _public_key, _message, _signature):
            raise RuntimeError("provider unavailable")

    store = PublicTrustStore()
    assert store.add(TrustedPublicKey("key-1", "s3-team", b"public")).is_ok
    unavailable = SignedRegistryIndexTrust(store, MissingProvider(), expected_origin="https://registry.fixture")
    assert unavailable.verify(original).error_or(None).code is SignedIndexErrorCode.VERIFIER_FAILURE
