# M2.86 IR Verifier Canary

## WHY_NOW

M2.84 provides the bounded S3-authored verifier and M2.85 composes qualified
IR identities. M2.86 gives the verifier an explicit, fail-closed selection
boundary without changing the production path.

## ARCHITECTURAL_DECISION

The Python verifier remains the default. The S3 candidate can run only when a
caller supplies explicit opt-in, the source lock matches exactly, and the
canonical differential agrees. Every other outcome reports a visible fallback
and retains the reference output.

## TEST_EVIDENCE

- Focused M2.86 contract: pending.
- Differential canary proof: pending.
- `compileall`: pending.
- `git diff --check`: pending.
- T1 affected profile: pending.
- T3 `m286` shard: pending.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
