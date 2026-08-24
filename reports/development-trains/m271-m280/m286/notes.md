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

- Focused M2.86 contract: PASS, 5 tests on Python 3.11, 3.12 and 3.13.
- Differential canary proof: PASS.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Impact metadata: PASS.
- T1 affected profile against `c0894900df06dddeaad75d85426baad7d423ca63`:
  PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m286` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `61cb18561d7c0ab4d7da53c10507f2188697b115`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
