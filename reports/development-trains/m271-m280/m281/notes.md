# M2.81 Canonical S3 IR Data Model

## WHY_NOW

M2.80 closed the bounded semantic train. M2.81 establishes the stable data
shape that later expression lowering, aggregate lowering and verification can
consume without changing the public IR 0.6.0 artifact.

## ARCHITECTURAL_DECISION

The model is immutable and bounded. Python owns the reference records and
canonical JSON contract; the S3 candidate receives fixed arrays and validates
shape only. CFG, type and semantic verification remain separate milestones.

## TEST_EVIDENCE

- Focused M2.81 contract: PASS, 4 tests on Python 3.11, 3.12 and 3.13.
- Differential reference/candidate proof: PASS.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Impact metadata: PASS.
- T1 affected profile against `aefbedc0a523bfe5c4cba72afdbd39a18f04f9a4`:
  PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m281` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `cb699aa8d2fdadb8c1e55ed8be8509f04822df30`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

QUALIFIED_LOCAL
