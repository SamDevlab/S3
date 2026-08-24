# M2.74 Bounded Place and Reference Candidate

## WHY_NOW

M2.73 closed the scalar type compatibility boundary. M2.74 adds the place and
reference capability checks needed before function and aggregate semantics can
be composed.

## ARCHITECTURAL_DECISION

The candidate uses a bounded descriptor instead of source-text identities. It
keeps value, shared-reference and mutable-reference storage classes explicit.
Readability, writability, initialization and addressability are independent
flags, and each operation returns an exact result class or a deterministic
rejection code.

## IMPLEMENTATION_SUMMARY

- Added `selfhost/semantic/place_reference_candidate.s3`.
- Added `bootstrap/s3/place_reference_candidate.py`.
- Added focused differential coverage for read/write, address, dereference,
  reborrow and fail-closed invalid requests.
- Added M2.74 smart-impact metadata.
- Preserved Python as the reference/default compiler path.

## TEST_EVIDENCE

- Focused M2.74 contract: PASS, 16 tests on Python 3.11.
- compileall: pending final qualification.
- diff check: pending final qualification.
- T1 affected profile: pending final qualification.
- T3 `m274` shard: pending final qualification.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

IMPLEMENTED_PENDING_QUALIFICATION
