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

- Focused M2.73 contract: PASS, 16 tests on Python 3.11, 3.12 and 3.13.
- `python -m compileall -q bootstrap/s3 tools`: PASS.
- `git diff --check`: PASS.
- T1 affected profile: PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m273` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `ad1f88cf99cd30b5b4e0b8f1bf3155cdbde4184e`.
- Documentation may receive a later candidate commit; source gates remain tied
  to the final tested source head.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

QUALIFIED_LOCAL
