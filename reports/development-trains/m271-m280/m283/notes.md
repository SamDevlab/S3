# M2.83 Call and Aggregate Lowering

## WHY_NOW

M2.82 lowered scalar expressions. M2.83 adds the independent call boundary
needed to preserve ordered arguments and multiple result cells.

## ARCHITECTURAL_DECISION

The milestone uses a `CallLoweringPlan` rather than changing the public
single-result `IRInstruction` model. This keeps aggregate result ordering
explicit while deferring composed IR closure and verifier integration.

## TEST_EVIDENCE

- Focused M2.83 contract: pending.
- Differential reference/candidate proof: pending.
- `compileall`: pending.
- `git diff --check`: pending.
- T1 affected profile: pending.
- T3 `m283` shard: pending.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
