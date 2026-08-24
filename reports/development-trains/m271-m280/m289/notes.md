# M2.89 Lowering Canary

## WHY_NOW

M2.88 supplies a composed lowering closure. M2.89 gives it an explicit
selection boundary while keeping the reference lowering path authoritative.

## ARCHITECTURAL_DECISION

Selection requires an exact source lock and a complete canonical differential.
Any mismatch or execution error returns the reference result with a visible
fallback reason. Default execution never probes the candidate.

## TEST_EVIDENCE

- Focused M2.89 contract: pending.
- Differential canary proof: pending.
- `compileall`: pending.
- `git diff --check`: pending.
- T1 affected profile: pending.
- T3 `m289` shard: pending.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
