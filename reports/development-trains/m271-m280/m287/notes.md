# M2.87 Lowering Checkpoint

## WHY_NOW

M2.82, M2.83 and M2.84 provide independent lowering and verification
contracts. M2.87 records the first bounded checkpoint where their outputs are
observed together.

## ARCHITECTURAL_DECISION

The checkpoint preserves each upstream result and adds a deterministic scalar
identity. It does not reconstruct producer decisions in the S3 candidate and
does not alter the production compiler path.

## TEST_EVIDENCE

- Focused M2.87 contract: pending.
- Differential checkpoint proof: pending.
- `compileall`: pending.
- `git diff --check`: pending.
- T1 affected profile: pending.
- T3 `m287` shard: pending.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
