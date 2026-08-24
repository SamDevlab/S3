# M2.83 Call and Aggregate Lowering

## WHY_NOW

M2.82 lowered scalar expressions. M2.83 adds the independent call boundary
needed to preserve ordered arguments and multiple result cells.

## ARCHITECTURAL_DECISION

The milestone uses a `CallLoweringPlan` rather than changing the public
single-result `IRInstruction` model. This keeps aggregate result ordering
explicit while deferring composed IR closure and verifier integration.

## TEST_EVIDENCE

- Focused M2.83 contract: PASS, 6 tests on Python 3.11, 3.12 and 3.13.
- Differential reference/candidate proof: PASS.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Impact metadata: PASS.
- T1 affected profile against `e3741284275a9bc4534fadc56bcdf5264d92fe2b`:
  PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m283` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `4a88ffae1d2974ede5d6486d80f4b98b782732ab`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

QUALIFIED_LOCAL
