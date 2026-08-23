# M2.58 Self-Hosting Differential Harness

## WHY_NOW

Future self-hosting components need exact, reproducible comparisons between a
Python reference and an S3 candidate. Test-only differential helpers do not
yet provide a reusable provenance and canonical-input result boundary.

## ARCHITECTURAL_DECISION

`DifferentialHarness` canonicalizes the input once, records its exact bytes and
SHA-256, then gives independently decoded equal inputs to the reference and
candidate callables. Provenance is required and canonicalized. Outputs must be
canonical JSON-shaped values; execution exceptions are normalized into typed
records and compared, while unsupported input/provenance/output values fail
closed. Mutation by one side cannot affect the other side's input.

## IMPLEMENTATION_SUMMARY

- Added exact-input, independently decoded differential execution.
- Added canonical input digest and provenance evidence to every result.
- Added deterministic output and structured-error comparison.
- Added fail-closed handling for unsupported values and missing provenance.
- Added M2.58 impact and shard metadata plus documentation.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- Focused M2.58 and existing differential support matrix: 20 selected,
  19 passed, 1 skipped, 0 failed. The skip is the pre-existing Linux-native
  differential execution test on Windows.
- M2.58 T2 at source HEAD
  `e8b57255484057b075a23a1d6dab5cef801411e2`: 1 selected, 1 passed,
  0 failed, 0 timed out.
- M2.58 T3 shard at the same source HEAD: 1 selected, 1 passed,
  0 failed, 0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone validates differential correctness
and provenance only; no performance claim is made.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

The harness executes hosted callables in one process. Native, cross-process,
and full self-hosted frontend integration remain later concerns.
