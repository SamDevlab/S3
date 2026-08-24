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

- Focused M2.78 contract: PASS, 6 tests on Python 3.11.
- Compileall, impact metadata, T1 and T3 remain pending until the candidate
  is committed.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

IMPLEMENTATION_GATES_PENDING
