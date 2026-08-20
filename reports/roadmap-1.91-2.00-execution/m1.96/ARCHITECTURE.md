# M1.96 Architecture: Signed Registry Index Trust

`SignedRegistryIndexTrust` verifies canonical index bytes through the existing
`PublicTrustStore` and an injected vetted verifier. The signed payload binds
origin, publisher, key identity, generation, and the exact index SHA-256. The
policy rejects unknown or revoked keys, publisher/origin mismatch, malformed
index documents, invalid signatures, provider failure, and generation
downgrade/replay.

No private-key path or custom signature algorithm is introduced. Provider
unavailability remains an explicit failure, not a pass or a fallback.
