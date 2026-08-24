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

- Focused M2.87 contract: PASS, 4 tests on Python 3.11, 3.12 and 3.13.
- Differential checkpoint proof: PASS.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Impact metadata: PASS.
- T1 affected profile against `dc37b7e620beda99d42757c5cb986d94015ef196`:
  PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m287` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `e71b4a3a391b3bfdd95051d20d40b22b844412a2`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
