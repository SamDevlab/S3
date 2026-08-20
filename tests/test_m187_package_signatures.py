from __future__ import annotations

import hashlib

import pytest

from bootstrap.s3.package_signatures import (
    CryptographyEd25519Verifier,
    PackageSignatureEnvelope,
    PackageSignatureService,
    PublicTrustStore,
    SignatureErrorCode,
    TrustedPublicKey,
    canonical_signing_payload,
)


class FixtureVerifier:
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        return hashlib.sha256(public_key + message).digest() == signature


def _signed(body: bytes, *, publisher: str = "s3-team", source: str = "https://registry.fixture") -> PackageSignatureEnvelope:
    digest = hashlib.sha256(body).hexdigest()
    unsigned = PackageSignatureEnvelope(
        "demo",
        "1.0.0",
        digest,
        publisher,
        "key-1",
        b"placeholder",
        (("source_commit", "fixture"),),
        source,
    )
    return PackageSignatureEnvelope(
        unsigned.name,
        unsigned.version,
        unsigned.digest,
        unsigned.publisher,
        unsigned.key_id,
        hashlib.sha256(b"public-key" + canonical_signing_payload(unsigned)).digest(),
        unsigned.provenance,
        unsigned.source,
    )


def test_package_signature_binds_digest_identity_source_key_and_provenance() -> None:
    body = b"package"
    store = PublicTrustStore()
    assert store.add(TrustedPublicKey("key-1", "s3-team", b"public-key")).is_ok
    service = PackageSignatureService(store, FixtureVerifier())
    verified = service.verify(_signed(body), body)
    assert verified.is_ok
    payload = verified.value_or(None).signing_payload
    assert b'"key_id":"key-1"' in payload
    assert b'"source":"https://registry.fixture"' in payload
    assert verified.value_or(None).body == body


def test_signature_rejects_unknown_key_publisher_digest_and_source_tampering() -> None:
    body = b"package"
    store = PublicTrustStore()
    assert store.add(TrustedPublicKey("key-1", "s3-team", b"public-key")).is_ok
    service = PackageSignatureService(store, FixtureVerifier())
    unknown = PackageSignatureEnvelope("demo", "1", hashlib.sha256(body).hexdigest(), "s3-team", "missing", b"x")
    assert service.verify(unknown, body).error_or(None).code is SignatureErrorCode.UNKNOWN_KEY
    assert service.verify(_signed(body, publisher="other"), body).error_or(None).code is SignatureErrorCode.PUBLISHER_MISMATCH
    assert service.verify(_signed(body), b"tampered").error_or(None).code is SignatureErrorCode.DIGEST_MISMATCH
    original = _signed(body)
    changed_source = PackageSignatureEnvelope(
        original.name,
        original.version,
        original.digest,
        original.publisher,
        original.key_id,
        original.signature,
        original.provenance,
        "https://other-registry.example",
    )
    assert service.verify(changed_source, body).error_or(None).code is SignatureErrorCode.INVALID_SIGNATURE


def test_public_trust_store_has_no_private_key_path_and_metadata_is_bounded() -> None:
    store = PublicTrustStore(max_keys=1)
    assert store.add(TrustedPublicKey("key-1", "s3-team", b"public")).is_ok
    assert store.add(TrustedPublicKey("key-2", "s3-team", b"public")).error_or(None).code is SignatureErrorCode.LIMIT


def test_production_ed25519_provider_verifies_real_signature_when_crypto_extra_is_available() -> None:
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    body = b"signed package"
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    unsigned = PackageSignatureEnvelope(
        "demo",
        "2.0.0",
        hashlib.sha256(body).hexdigest(),
        "s3-team",
        "ed25519-key",
        b"placeholder",
        (("compiler", "fixture"),),
        "https://registry.fixture",
    )
    signature = private.sign(canonical_signing_payload(unsigned))
    envelope = PackageSignatureEnvelope(
        unsigned.name,
        unsigned.version,
        unsigned.digest,
        unsigned.publisher,
        unsigned.key_id,
        signature,
        unsigned.provenance,
        unsigned.source,
    )
    store = PublicTrustStore()
    assert store.add(TrustedPublicKey("ed25519-key", "s3-team", public)).is_ok
    service = PackageSignatureService(store, CryptographyEd25519Verifier())
    assert service.verify(envelope, body).is_ok
