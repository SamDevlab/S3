# M2.81 Canonical S3 IR Data Model

## WHY_NOW

M2.80 closed the bounded semantic train. M2.81 establishes the stable data
shape that later expression lowering, aggregate lowering and verification can
consume without changing the public IR 0.6.0 artifact.

## ARCHITECTURAL_DECISION

The model is immutable and bounded. Python owns the reference records and
canonical JSON contract; the S3 candidate receives fixed arrays and validates
shape only. CFG, type and semantic verification remain separate milestones.

## TEST_EVIDENCE

- Focused M2.81 contract: pending.
- Differential reference/candidate proof: pending.
- `compileall`: pending.
- `git diff --check`: pending.
- T1 affected profile: pending.
- T3 `m281` shard: pending.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
