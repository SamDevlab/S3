# M2.91 Assembly Emission Candidate

## WHY_NOW

M2.90 closes the bounded IR/lowering checkpoint. M2.91 begins the emission
train with a deliberately small verified linear Assembly subset.

## ARCHITECTURAL_DECISION

The Python Assembly text remains the exact reference and is reparsed before
acceptance. The S3 candidate consumes only the bounded emission plan and
reproduces its deterministic identity. Production emission remains unchanged.

## TEST_EVIDENCE

- Focused M2.91 contract: pending.
- Emission differential proof: pending.
- Assembly reparse: pending.
- `compileall`: pending.
- `git diff --check`: pending.
- T1 affected profile: pending.
- T3 `m291` shard: pending.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
