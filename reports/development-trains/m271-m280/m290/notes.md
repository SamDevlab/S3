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

- Focused M2.90 contract: PASS, 3 tests on Python 3.11, 3.12 and 3.13.
- Combined checkpoint proof: PASS.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Impact metadata: PASS.
- T1 affected profile against `cf43cbe94eac1675e1554c8fbafd68fab4e28ff4`:
  PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m290` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `3c90f453e67b3a7f300ed57713db32e14ef3fd62`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
