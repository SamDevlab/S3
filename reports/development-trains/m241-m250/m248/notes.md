# M2.48 Experiment-to-Production Promotion Framework

## WHY_NOW

The repository contains experimental compiler and backend components that must
remain useful for controlled evaluation without becoming accidental production
paths. M2.48 makes that boundary executable and reviewable.

## ARCHITECTURAL_DECISION

Promotion is a decision boundary, not an implicit feature switch. Every
candidate remains OFF by default and requires explicit opt-in. The candidate's
observed source SHA must match its pinned source lock. Eligibility, correctness
evidence, and structural evidence are independent gates, and a reference
fallback is mandatory. Any source-lock mismatch or failed gate resolves to
`FALLBACK`; only an explicitly opted-in candidate with every gate passing is
`CANDIDATE_SELECTED`.

The framework does not wire Compact EA, ABL V2.x, or any other experimental
component into a default path. It records the policy and decision without
claiming production promotion or performance improvement.

## IMPLEMENTATION_SUMMARY

- Added `bootstrap.s3.experiment_promotion` with typed contract, source-lock
  validation, explicit opt-in selection, and fail-closed fallback decisions.
- Added regressions for OFF-by-default behavior, successful explicit selection,
  source drift, failed gates, unavailable fallback, and accidental default
  activation.
- Added a public policy note and M2.48 impact/shard metadata.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- Focused promotion and adjacent policy matrix: 23 selected, 23 passed,
  0 failed, 0 timed out.
- M2.48 T2 at source HEAD
  `10649c0b5173a059f75a29f719cd3211d4addfec`: 1 selected, 1 passed,
  0 failed, 0 timed out.
- M2.48 T3 shard at the same source HEAD: 1 selected, 1 passed, 0 failed,
  0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. The framework defines eligibility and safety policy;
it makes no runtime or native performance claim.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

The framework does not itself prove candidate correctness or structural
equivalence. It requires those proofs as inputs and rejects incomplete or
drifted evidence.
