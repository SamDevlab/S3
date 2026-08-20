# M1.87 Architecture

M1.87 verifies package authenticity after content-address verification. The canonical signing payload binds package name, version, SHA-256 digest, publisher, key id, canonical HTTPS source identity, and bounded unique provenance metadata. Signing ambiguous human-formatted text is avoided by deterministic JSON serialization.

The selected production algorithm/provider is **Ed25519 via the `cryptography` package** (`CryptographyEd25519Verifier`). The bootstrap core does not implement signature mathematics and has no home-grown fallback. `cryptography` is an optional `crypto` project extra so minimal/offline bootstrap use remains possible; attempting production verification without the provider fails closed through the verifier boundary.

The repository owns only bounded public-key trust records. There is no private-key generation/storage path. Unknown keys, publisher mismatch, digest mismatch, source/provenance tampering, oversized metadata/signatures, invalid Ed25519 signatures, and verifier/provider failures are explicit `Result` errors. The deterministic fixture verifier remains unit-test-only and is not represented as a production crypto certificate.

A provider-available focused test generates an ephemeral Ed25519 fixture key, signs the canonical payload, and verifies it through the production adapter. The private fixture key exists only in test process memory and is not committed.
