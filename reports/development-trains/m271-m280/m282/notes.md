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

- Focused M2.82 contract: pending.
- Differential reference/candidate proof: pending.
- `compileall`: pending.
- `git diff --check`: pending.
- T1 affected profile: pending.
- T3 `m282` shard: pending.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
