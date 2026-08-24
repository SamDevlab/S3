# M2.89 Lowering Canary

## WHY_NOW

M2.88 supplies a composed lowering closure. M2.89 gives it an explicit
selection boundary while keeping the reference lowering path authoritative.

## ARCHITECTURAL_DECISION

Selection requires an exact source lock and a complete canonical differential.
Any mismatch or execution error returns the reference result with a visible
fallback reason. Default execution never probes the candidate.

## TEST_EVIDENCE

- Focused M2.89 contract: PASS, 5 tests on Python 3.11, 3.12 and 3.13.
- Differential canary proof: PASS.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Impact metadata: PASS.
- T1 affected profile against `cb14b950bcb44a040e560a794c4894f77f06c8d0`:
  PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m289` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `624847164143a24cc552555740306963f59e0290`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
