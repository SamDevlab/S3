# M2.82 Canonical Expression Lowering

## WHY_NOW

M2.81 fixed the bounded IR data shape. M2.82 adds the first lowering producer
for that shape while keeping expression coverage deliberately small and
independent from production lowering.

## ARCHITECTURAL_DECISION

Post-order nodes make dependencies explicit and permit a bounded S3 loop to
assign deterministic result registers. The reference constructs the M2.81
canonical records; the S3 candidate computes the same identity. Verifier and
promotion responsibilities remain separate.

## TEST_EVIDENCE

- Focused M2.82 contract: PASS, 6 tests on Python 3.11, 3.12 and 3.13.
- Differential reference/candidate proof: PASS.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Impact metadata: PASS.
- T1 affected profile against `b6fb807e439ff9eb0ee6684d0da4bb9c4667c134`:
  PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m282` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `8083a259e742ecbc052127cd747a17897ad20095`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

QUALIFIED_LOCAL
