# M2.91 Assembly Emission Candidate

## WHY_NOW

M2.90 closes the bounded IR/lowering checkpoint. M2.91 begins the emission
train with a deliberately small verified linear Assembly subset.

## ARCHITECTURAL_DECISION

The Python Assembly text remains the exact reference and is reparsed before
acceptance. The S3 candidate consumes only the bounded emission plan and
reproduces its deterministic identity. Production emission remains unchanged.

## TEST_EVIDENCE

- Focused M2.91 contract: PASS, 4 tests on Python 3.11, 3.12 and 3.13.
- Emission differential proof: PASS.
- Assembly reparse: PASS.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Impact metadata: PASS.
- T1 affected profile against `3c049e92575874b7f06bc10ac0fb3d0ba4861277`:
  PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m291` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `cffc79613632484b4f93c0d2d7bcbc00af7a93d8`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
