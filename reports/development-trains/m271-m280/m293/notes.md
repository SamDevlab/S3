# M2.93 Native Emission Boundary

## WHY_NOW

M2.92 verifies emitted Assembly. M2.93 records the explicit boundary at which
an external host assembler or linker would be required.

## ARCHITECTURAL_DECISION

The S3 candidate prepares only a deterministic target-labelled plan. It never
silently invokes a host tool, fabricates native bytes or falls back to another
target.

## TEST_EVIDENCE

- Focused M2.93 contract: pending.
- Target matrix: pending.
- `compileall`: pending.
- `git diff --check`: pending.
- T1 affected profile: pending.
- T3 `m293` shard: pending.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
