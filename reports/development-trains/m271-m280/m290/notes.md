# M2.90 IR and Lowering Self-Hosting Checkpoint

## WHY_NOW

M2.84-M2.89 establish bounded verifier, lowering, composition and canary
contracts. M2.90 records their combined selection state before the emission
and driver train.

## ARCHITECTURAL_DECISION

The verifier and lowering boundaries remain independent and fail closed. The
checkpoint is complete only for the bounded candidate subset; it is not a
claim that the compiler is fully self-hosted.

## TEST_EVIDENCE

- Focused M2.90 contract: pending.
- Combined checkpoint proof: pending.
- `compileall`: pending.
- `git diff --check`: pending.
- T1 affected profile: pending.
- T3 `m290` shard: pending.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
