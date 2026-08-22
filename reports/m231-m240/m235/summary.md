# M2.35 Signed Registry and Supply Chain

`M2_35_SUPPLY_CHAIN=PARTIAL`

The resolver can consume only an authenticated `VerifiedRegistryIndex`, and
mutation of the unsigned index after verification does not affect resolution.
Unvetted verifier providers fail closed. Package identity, digest, cache, and
path-boundary focused tests pass. End-to-end vetted Ed25519 publication is
deferred because the provider is unavailable in this environment; there is no
unsigned or trust-downgrade fallback.

- `SIGNED_INDEX=PASS`
- `TRUST_ROOT=PASS`
- `CONTENT_HASH=PASS`
- `TAMPER_REJECTION=PASS`
- `CACHE_SECURITY=PASS`
- `OFFLINE_CACHE=PASS_FOR_EXISTING_CONTRACT`
- `RESOLUTION_REPRODUCIBILITY=PASS`
