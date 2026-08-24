# M2.79 Semantic Candidate Canary

## WHY_NOW

M2.78 composed the semantic kernels but did not select them for any compiler
path. M2.79 establishes the explicit, observable routing boundary needed for
the M2.80 semantic checkpoint.

## ARCHITECTURAL_DECISION

The canary uses the shared promotion contract and canonical differential
harness. It is off by default. Opt-in selection is permitted only after the
source lock, canonical input/output, reference execution and candidate
execution all agree. Candidate errors, reference errors and canonical output
mismatches return a visible reference fallback with a stable reason.

## IMPLEMENTATION_SUMMARY

- Added `bootstrap/s3/semantic_canary.py`.
- Added focused routing and fail-closed fallback coverage.
- Added M2.79 smart-impact metadata and milestone documentation.
- Preserved the Python reference as the default compiler path.

## TEST_EVIDENCE

- Focused M2.79 contract: PASS, 5 tests on Python 3.11, 3.12 and 3.13.
- Regression against the composed M2.78 candidate: PASS in all three runtimes.
- `python -m compileall -q bootstrap/s3 tools`: PASS.
- `git diff --check`: PASS.
- T1 affected profile: PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m279` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `e5d017c8e15960922119258ee8b73445a06eaffb`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

QUALIFIED_LOCAL
