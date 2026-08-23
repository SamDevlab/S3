from __future__ import annotations

import base64
import hashlib
import json

import pytest

from bootstrap.s3.package_signatures import (
    CryptographyEd25519Verifier,
    PackageSignatureEnvelope,
    PublicTrustStore,
    TrustedPublicKey,
    canonical_signing_payload,
)
from bootstrap.s3.signed_registry_client import (
    SignedRegistryError,
    SignedRegistryErrorCode,
    SignedRegistryV2Client,
)
from bootstrap.s3.signed_registry_index import (
    SignedIndexEnvelope,
    SignedRegistryIndexTrust,
    VerifiedRegistryIndex,
    canonical_signed_index_payload,
)


def _unsigned_index(document: dict[str, object]) -> VerifiedRegistryIndex:
    index = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    envelope = SignedIndexEnvelope(
        "https://registry.fixture",
        "s3-team",
        "key-1",
        1,
        index,
        b"index-signature",
    )
    return VerifiedRegistryIndex(envelope, document, canonical_signed_index_payload(envelope))


def test_signed_registry_rejects_unsigned_package_downgrade_before_fetch(tmp_path) -> None:
    document = {
        "format": "s3.registry.index.v2",
        "origin": "https://registry.fixture",
        "packages": [{
            "name": "demo",
            "version": "1.0.0",
            "sha256": hashlib.sha256(b"package").hexdigest(),
            "object": "objects/demo.tar",
            "dependencies": [],
        }],
    }
    store = PublicTrustStore()
    with pytest.raises(SignedRegistryError, match="signed envelope") as failure:
        SignedRegistryV2Client.from_verified_index(tmp_path, _unsigned_index(document), store)
    assert failure.value.code is SignedRegistryErrorCode.UNSIGNED_DOWNGRADE


def test_signed_registry_rejects_invalid_signature_encoding_before_provider_use(tmp_path) -> None:
    document = {
        "format": "s3.registry.index.v2",
        "origin": "https://registry.fixture",
        "packages": [{
            "name": "demo",
            "version": "1.0.0",
            "sha256": "0" * 64,
            "object": "objects/demo.tar",
            "dependencies": [],
            "signature": {
                "publisher": "s3-team",
                "key_id": "key-1",
                "signature_b64": "not-base64",
                "source": "https://registry.fixture",
            },
        }],
    }
    with pytest.raises(SignedRegistryError, match="encoding is invalid"):
        SignedRegistryV2Client.from_verified_index(tmp_path, _unsigned_index(document), PublicTrustStore())


def _real_client(tmp_path, *, package_key_id: str = "key-1", signature_override: bytes | None = None):
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    body = b"signed package bytes"
    source = "https://registry.fixture"
    package_digest = hashlib.sha256(body).hexdigest()
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    package_unsigned = PackageSignatureEnvelope(
        "demo",
        "1.0.0",
        package_digest,
        "s3-team",
        "key-1",
        b"placeholder",
        (("source_commit", "fixture"),),
        source,
    )
    package_signature = signature_override or private.sign(canonical_signing_payload(package_unsigned))
    document = {
        "format": "s3.registry.index.v2",
        "origin": source,
        "packages": [{
            "name": "demo",
            "version": "1.0.0",
            "sha256": package_digest,
            "object": "objects/demo.tar",
            "dependencies": [],
            "signature": {
                "publisher": "s3-team",
                "key_id": package_key_id,
                "signature_b64": base64.b64encode(package_signature).decode("ascii"),
                "provenance": {"source_commit": "fixture"},
                "source": source,
            },
        }],
    }
    index = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    index_unsigned = SignedIndexEnvelope(source, "s3-team", "key-1", 1, index, b"placeholder")
    index_envelope = SignedIndexEnvelope(
        source,
        "s3-team",
        "key-1",
        1,
        index,
        private.sign(canonical_signed_index_payload(index_unsigned)),
    )
    store = PublicTrustStore()
    assert store.add(TrustedPublicKey("key-1", "s3-team", public)).is_ok
    trust = SignedRegistryIndexTrust(
        store,
        CryptographyEd25519Verifier(),
        expected_origin=source,
    )
    verified_result = trust.verify_vetted(index_envelope)
    assert verified_result.is_ok
    verified = verified_result.value_or(None)
    assert verified is not None
    root = tmp_path / "registry"
    (root / "objects").mkdir(parents=True)
    (root / "objects" / "demo.tar").write_bytes(body)
    client = SignedRegistryV2Client.from_verified_index(root, verified, store)
    return client, client.resolve("demo", "1.0.0"), root, body


def test_real_ed25519_registry_verification_supports_cache_and_offline_reuse(tmp_path) -> None:
    client, lock, root, body = _real_client(tmp_path)
    verified = client.fetch_verified(lock)
    assert verified.body == body
    assert client.fetch(lock) == body
    (root / "objects" / "demo.tar").unlink()
    assert client.fetch(lock) == body
    assert client.read_only
    assert client.provider_identity == "cryptography:Ed25519"


def test_real_ed25519_registry_rejects_object_tampering(tmp_path) -> None:
    client, lock, root, _body = _real_client(tmp_path)
    (root / "objects" / "demo.tar").write_bytes(b"tampered")
    with pytest.raises(SignedRegistryError, match="digest mismatch") as failure:
        client.fetch(lock)
    assert failure.value.code is SignedRegistryErrorCode.REGISTRY_FAILURE


def test_real_ed25519_registry_rejects_signature_and_wrong_key(tmp_path) -> None:
    client, lock, _root, _body = _real_client(tmp_path, signature_override=b"x" * 64)
    with pytest.raises(SignedRegistryError, match="invalid_signature") as invalid:
        client.fetch(lock)
    assert invalid.value.code is SignedRegistryErrorCode.SIGNATURE_FAILURE

    wrong_key_client, wrong_key_lock, _root, _body = _real_client(tmp_path / "wrong-key", package_key_id="missing")
    with pytest.raises(SignedRegistryError, match="unknown_key") as wrong_key:
        wrong_key_client.fetch(wrong_key_lock)
    assert wrong_key.value.code is SignedRegistryErrorCode.SIGNATURE_FAILURE
