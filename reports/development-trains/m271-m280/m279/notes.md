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

- Focused M2.79 contract: PASS, 5 tests on Python 3.11.
- Compileall, impact metadata, T1 and T3 remain pending until the candidate
  is committed.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

IMPLEMENTATION_GATES_PENDING
