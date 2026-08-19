# M1.87 Architecture

M1.87 verifies package signatures and provenance after the M1.86 content
address check. The package envelope binds name, version, SHA-256, publisher,
key identity, and bounded provenance metadata into one canonical byte string.

The compiler owns only a public-key trust store and a narrow
`VettedSignatureVerifier` protocol. Signature math is delegated to a vetted
host crypto provider; this repository does not generate, persist, or accept
private keys. Unknown key identities, publisher mismatches, digest mismatches,
malformed metadata, and verifier failures are rejected through explicit
`Result` errors. Verified bytes are immutable and can be passed to the bounded
registry cache.

The test verifier is a deterministic fixture double, not a production crypto
implementation and not evidence of a cryptographic execution certificate.
