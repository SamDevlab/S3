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
- Compileall, diff check, smart affected and shard qualification: pending.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

IMPLEMENTED_PENDING_QUALIFICATION
