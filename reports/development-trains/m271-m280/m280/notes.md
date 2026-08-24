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

- Focused checkpoint contract: PASS, 3 tests on Python 3.11, 3.12 and 3.13.
- Level-C `level-c-semantic`: PASS, 9 selected, 9 passed, 0 failed, 0 timed
  out, covering M2.71 through M2.79 in order.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Impact metadata: PASS.
- T1 affected profile against `109364b9fb2ea8f9611266827ddd20b0cb61d97c`:
  PASS, 5 selected, 5 passed, 0 failed, 0 timed out.
- T3 `m280` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `c1dc581da85c5cabb0e21ede1f06c662f70096ba`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

QUALIFIED_LOCAL
