# M2.78 Composed Semantic Closure

## WHY_NOW

M2.71 through M2.77 established separate bounded semantic kernels. M2.78
connects those kernels behind the canonical composed contract required before
opt-in candidate routing.

## ARCHITECTURAL_DECISION

The S3 candidate is the executing composition. The Python adapter validates
container bounds and serializes raw arrays, while the Python reference calls
the existing reference semantics only for differential comparison. Namespace
prefixes keep the previously qualified S3 functions distinct when composed.

Accepted output folds component results and fixed-layout identity lanes into a
bounded deterministic identity. Rejection is fail-closed at the first named
semantic stage.

## IMPLEMENTATION_SUMMARY

- Added `selfhost/semantic/semantic_closure_candidate.s3`.
- Added `bootstrap/s3/semantic_closure_candidate.py`.
- Added focused differential coverage for valid composition, stage rejection,
  bounds and layout identity sensitivity.
- Added M2.78 smart-impact metadata.
- Preserved the Python reference/default compiler path.

## TEST_EVIDENCE

- Focused M2.78 contract: PASS, 6 tests on Python 3.11, 3.12 and 3.13.
- Combined M2.77 and M2.78 regression: PASS, 17 tests on all three runtimes.
- `python -m compileall -q bootstrap/s3 tools`: PASS.
- `git diff --check`: PASS.
- T1 affected profile: PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m278` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `9347f57cd4d8123b1be9a272000ec328615719b2`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

QUALIFIED_LOCAL
