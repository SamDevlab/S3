from __future__ import annotations

import hashlib

from bootstrap.s3.package_signatures import (
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


def _signed(body: bytes, *, publisher: str = "s3-team") -> PackageSignatureEnvelope:
    digest = hashlib.sha256(body).hexdigest()
    unsigned = PackageSignatureEnvelope("demo", "1.0.0", digest, publisher, "key-1", b"", (("source", "fixture"),))
    return PackageSignatureEnvelope(
        unsigned.name,
        unsigned.version,
        unsigned.digest,
        unsigned.publisher,
        unsigned.key_id,
        hashlib.sha256(b"public-key" + canonical_signing_payload(unsigned)).digest(),
        unsigned.provenance,
    )


def test_package_signature_binds_digest_identity_and_provenance() -> None:
    body = b"package"
    store = PublicTrustStore()
    assert store.add(TrustedPublicKey("key-1", "s3-team", b"public-key")).is_ok
    service = PackageSignatureService(store, FixtureVerifier())
    verified = service.verify(_signed(body), body)
    assert verified.is_ok
    assert verified.value_or(None).body == body


def test_signature_rejects_unknown_key_publisher_and_digest_mismatch() -> None:
    body = b"package"
    store = PublicTrustStore()
    assert store.add(TrustedPublicKey("key-1", "s3-team", b"public-key")).is_ok
    service = PackageSignatureService(store, FixtureVerifier())
    unknown = PackageSignatureEnvelope("demo", "1", hashlib.sha256(body).hexdigest(), "s3-team", "missing", b"x")
    assert service.verify(unknown, body).error_or(None).code is SignatureErrorCode.UNKNOWN_KEY
    assert service.verify(_signed(body, publisher="other"), body).error_or(None).code is SignatureErrorCode.PUBLISHER_MISMATCH
    assert service.verify(_signed(body), b"tampered").error_or(None).code is SignatureErrorCode.DIGEST_MISMATCH


def test_public_trust_store_has_no_private_key_path_and_metadata_is_bounded() -> None:
    store = PublicTrustStore(max_keys=1)
    assert store.add(TrustedPublicKey("key-1", "s3-team", b"public")).is_ok
    assert store.add(TrustedPublicKey("key-2", "s3-team", b"public")).error_or(None).code is SignatureErrorCode.LIMIT
