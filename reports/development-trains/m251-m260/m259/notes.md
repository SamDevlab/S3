# M2.59 Candidate Promotion Integration

## WHY_NOW

The shared promotion framework already enforced source locking, explicit opt-in,
fallback availability, and off-by-default behavior. Self-hosted candidates now
also need one reusable boundary that binds those decisions to canonical
differential evidence rather than to unvalidated metadata.

## ARCHITECTURAL_DECISION

`CandidateMetadata` validates a candidate component, source lock, canonical
provenance, exact-input digest, and one `DifferentialResult`. The provenance
must identify the same component and source lock as the metadata. A matching
differential result becomes the shared contract's correctness PASS; a mismatch
becomes a correctness failure and selects the existing fallback. The final
decision still comes from `PromotionContract` and therefore requires exact
observed source plus explicit opt-in.

## IMPLEMENTATION_SUMMARY

- Added candidate metadata validation for canonical input and provenance.
- Added source/component binding checks and digest verification.
- Routed candidate decisions through the existing fail-closed promotion
  framework.
- Preserved off-by-default behavior, fallback availability, and no native or
  performance claims.
- Added M2.59 impact and shard metadata.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS.
- Focused promotion, cross-target, canonical serialization, differential, and
  impact tests: 59 selected, 59 passed, 0 skipped, 0 failed, 0 timed out.
- M2.59 T2 at source HEAD `0c44a2e0c1feaa3c0025ed6d31719fc26ad81bb8`:
  1 selected, 1 passed, 0 failed, 0 timed out.
- M2.59 T3 shard at the same source HEAD: 1 selected, 1 passed, 0 failed,
  0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone adds evidence validation and
promotion routing only; no performance claim is made.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## STATUS

M2.59 is complete and ready for review. M2.60 remains the next integration
checkpoint.
