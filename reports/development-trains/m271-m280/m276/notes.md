# M2.76 Bounded Record, Enum and Fixed-Layout Candidate

## WHY_NOW

M2.75 closed bounded function signatures and calls. M2.76 adds the fixed cell
counts and deterministic layout identities needed before semantic values can be
composed across records and enums.

## ARCHITECTURAL_DECISION

The candidate consumes canonical fixed arrays of scalar type IDs instead of
nominal names. Record fields retain source order. Enum layout is tag-first and
uses the largest variant payload width, with inactive slots retained. Two
independent deterministic identity lanes make ordering and payload changes
observable without claiming a cryptographic identity.

## IMPLEMENTATION_SUMMARY

- Added `selfhost/semantic/fixed_layout_candidate.s3`.
- Added `bootstrap/s3/fixed_layout_candidate.py`.
- Added focused differential coverage for record and enum layout counts,
  identity determinism, order sensitivity and fail-closed bounds.
- Added M2.76 smart-impact metadata.
- Preserved Python as the reference/default compiler path.

## TEST_EVIDENCE

- Focused M2.76 contract: PASS, 8 tests on Python 3.11.
- Focused M2.76 contract: PASS, 8 tests on Python 3.11, 3.12 and 3.13.
- `python -m compileall -q bootstrap/s3 tools`: PASS.
- `git diff --check`: PASS.
- T1 affected profile: PASS, 4 selected, 4 passed, 0 failed, 0 timed out.
- T3 `m276` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `95e3dae41596c6d2a2335e354acca17ca99e0cb1`.
- Documentation may receive a later candidate commit; source gates remain tied
  to the final tested source head.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

QUALIFIED_LOCAL
