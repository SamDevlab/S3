# M2.73 Bounded Scalar Type Checking Candidate

## WHY_NOW

M2.71 established exact symbol slots and M2.72 added bounded lexical scope
resolution. M2.73 supplies the next semantic dependency: scalar expression and
conversion compatibility without delegating the decision to Python.

## ARCHITECTURAL_DECISION

The candidate uses stable numeric IDs for the four scalar domains and a single
canonical operation contract. Accepted results carry the resulting scalar type;
rejected results carry a bounded diagnostic code. Assignment is exact, binary
operations require matching scalar domains, comparisons return `trit`, and
numeric conversions follow the existing semantic conversion matrix.

## IMPLEMENTATION_SUMMARY

- Added `selfhost/semantic/scalar_type_checking_candidate.s3`.
- Added `bootstrap/s3/scalar_type_checking_candidate.py`.
- Added focused differential coverage for assignment, arithmetic, comparisons,
  explicit conversions and fail-closed invalid requests.
- Added M2.73 smart-impact metadata.
- Preserved Python as the reference/default compiler path.

## TEST_EVIDENCE

- Focused M2.73 contract: PASS, 16 tests on Python 3.11.
- compileall: pending final qualification.
- diff check: pending final qualification.
- T1 affected profile: pending final qualification.
- T3 `m273` shard: pending final qualification.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

IMPLEMENTED_PENDING_QUALIFICATION
