# M2.85 Composed IR Closure

## WHY_NOW

M2.82 and M2.83 provide independent expression and call producers. M2.85
proves that their canonical identities can be composed without hiding either
component's evidence.

## ARCHITECTURAL_DECISION

The S3 closure accepts already-produced identities. It is not a replacement
for the producer kernels and it does not enable default execution. The next
milestone owns explicit canary routing.

## TEST_EVIDENCE

- Focused M2.85 contract: pending.
- Differential composition proof: pending.
- `compileall`: pending.
- `git diff --check`: pending.
- T1 affected profile: pending.
- T3 `m285` shard: pending.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
