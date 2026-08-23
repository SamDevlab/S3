# M2.45 Ed25519 Signed Registry End-to-End

## WHY_NOW

M2.44 established bounded protocol decoding. Registry consumption now needs a
single authenticated path from a trusted signed index to a content-addressed
package object, without permitting an unsigned fallback.

## ARCHITECTURAL_DECISION

`SignedRegistryV2Client` accepts only a `VerifiedRegistryIndex`, requires the
vetted `cryptography` Ed25519 provider, and requires every package entry to
carry a signed envelope. Package signatures bind name, version, digest,
publisher, key id, provenance, and registry source. The resolver first checks
the object hash and then verifies the package signature. Only bytes already
checked by the bounded resolver may be reused from its offline cache.

No custom cryptographic primitive or unsigned downgrade path was added.

## IMPLEMENTATION_SUMMARY

- Added signed package-envelope parsing with strict base64 and metadata
  validation.
- Added an Ed25519-only end-to-end registry client over the verified v2 index
  path.
- Rejected missing signatures, malformed envelopes, source replay, object
  tampering, invalid signatures, and unknown keys.
- Preserved read-only operation and verified offline/cache reuse.
- Added M2.45 impact and shard metadata.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- `python -m json.tool tests/test-impact.json`: PASS
- Focused registry/signature matrix: 31 passed, 4 skipped, 0 failed.
- T2 M2.45 at source HEAD
  `078705eaf357aea1492d71305de091eb45998d02`: 4 selected, 4 passed, 0
  failed, 0 timed out.
- T3 M2.45 shard at the same source HEAD: 4 selected, 4 passed, 0 failed,
  0 timed out.
- `git diff --check`: PASS.

## PROVIDER_EVIDENCE

The local Windows Python and the configured Linux x86-64 Python both report
`ed25519_available=false` and `ed25519_provider=unavailable`. The actual
cryptography-backed Ed25519 cases are therefore environment-deferred. The
implementation fails closed when that provider is absent; it does not replace
it with a fixture verifier or custom primitive.

## LEVEL_H

`ENVIRONMENT_DEFERRED_PROVIDER_UNAVAILABLE`. Existing policy and fail-closed
contracts passed; actual provider-backed signature execution remains required
when the vetted dependency is supplied.

## BENCHMARK_RELEVANCE

None. This milestone certifies registry authenticity and offline integrity;
no performance claim is made.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

The current release surface remains read-only and production registry/network
publishing remains outside this milestone. Provider-backed Ed25519 execution
cannot be certified on the current Windows or Linux environments until
`cryptography` is available.
