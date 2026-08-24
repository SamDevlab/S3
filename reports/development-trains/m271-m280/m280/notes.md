# M2.80 Semantic Self-Hosting Level-C Checkpoint

## WHY_NOW

M2.71-M2.79 provide the bounded semantic kernels, composed contract and
explicit canary boundary. M2.80 verifies their ordered train profile before
the roadmap moves to IR and lowering self-hosting.

## ARCHITECTURAL_DECISION

Level-C is a qualification profile, not a production promotion. It covers
the nine semantic milestone test files in order and excludes T4. The
semantic candidate remains available only through M2.79 explicit opt-in;
Python remains the default reference path with visible fallback.

## IMPLEMENTATION_SUMMARY

- Added the `level-c-semantic` smart-test profile.
- Added the M2.80 checkpoint contract test.
- Added checkpoint documentation and machine-readable evidence.
- Kept benchmarks, native execution and full T4 outside this semantic gate.

## TEST_EVIDENCE

- Focused checkpoint contract: PASS, 3 tests on Python 3.11.
- Level-C, compileall, impact metadata, T1 and T3 remain pending until the
  checkpoint is committed.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

CHECKPOINT_GATES_PENDING
