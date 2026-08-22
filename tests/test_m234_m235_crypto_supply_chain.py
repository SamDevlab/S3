from __future__ import annotations

import hashlib
import json

from bootstrap.s3.crypto_providers import discover_crypto_providers
from bootstrap.s3.package_signatures import PublicTrustStore, TrustedPublicKey
from bootstrap.s3.registry_v2 import RegistryV2Client
from bootstrap.s3.signed_registry_index import (
    SignedIndexEnvelope,
    SignedIndexErrorCode,
    SignedRegistryIndexTrust,
    canonical_signed_index_payload,
)


class FixtureVerifier:
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        return hashlib.sha256(public_key + message).digest() == signature


def _signed_index(index: bytes) -> SignedIndexEnvelope:
    unsigned = SignedIndexEnvelope("https://registry.fixture", "s3-team", "key-1", 1, index, b"placeholder")
    return SignedIndexEnvelope(
        unsigned.origin,
        unsigned.publisher,
        unsigned.key_id,
        unsigned.generation,
        unsigned.index,
        hashlib.sha256(b"public" + canonical_signed_index_payload(unsigned)).digest(),
    )


def test_crypto_provider_inventory_is_explicit_and_deterministic() -> None:
    first = discover_crypto_providers()
    second = discover_crypto_providers()
    assert first.json == second.json
    assert first.tls_provider
    assert isinstance(first.tls_available, bool)
    assert isinstance(first.ed25519_available, bool)


def test_signed_registry_resolver_consumes_only_verified_index(tmp_path) -> None:
    body = b"package"
    digest = hashlib.sha256(body).hexdigest()
    document = {
        "format": "s3.registry.index.v2",
        "origin": "https://registry.fixture",
        "packages": [{"name": "demo", "version": "1.0", "sha256": digest, "object": "objects/demo.tar", "dependencies": []}],
    }
    index = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    (tmp_path / "objects").mkdir()
    (tmp_path / "objects" / "demo.tar").write_bytes(body)
    (tmp_path / "index.json").write_bytes(index)
    store = PublicTrustStore()
    assert store.add(TrustedPublicKey("key-1", "s3-team", b"public")).is_ok
    trust = SignedRegistryIndexTrust(store, FixtureVerifier(), expected_origin="https://registry.fixture")
    verified = trust.verify(_signed_index(index))
    assert verified.is_ok
    client = RegistryV2Client.from_verified_index(tmp_path, verified.value_or(None))
    assert client.fetch(client.resolve("demo", "1.0").root) == body

    # A later unsigned file mutation cannot replace the authenticated document.
    (tmp_path / "index.json").write_bytes(b"not trusted")
    assert client.resolve("demo", "1.0").root.sha256 == digest


def test_signed_index_exposes_fail_closed_vetted_provider_gate() -> None:
    store = PublicTrustStore()
    assert store.add(TrustedPublicKey("key-1", "s3-team", b"public")).is_ok
    trust = SignedRegistryIndexTrust(store, FixtureVerifier(), expected_origin="https://registry.fixture")
    assert not trust.provider_is_vetted
    result = trust.verify_vetted(_signed_index(b'{"format":"s3.registry.index.v2","origin":"https://registry.fixture","packages":[]}'))
    assert result.error_or(None).code is SignedIndexErrorCode.VERIFIER_FAILURE
