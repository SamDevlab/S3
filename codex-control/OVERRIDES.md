# Live overrides

CONTROL_REVISION: 35

## CURRENT TASK — STAGE1 SEMANTIC VALUE NAMESPACE BANKING

Read:

```text
codex-control/STAGE1_REV35_VALUE_NAMESPACE_BANKING.md
```

Current implementation branch:

```text
recovery/pr268-stage1-lanes-20260828
```

Reported implementation HEAD:

```text
1ec76af89992f119865a370488593ad5c85c4c49
```

Current evidence:

```text
S1.1 Foundation = PASS
S1.2 typed-constant mechanism/fixtures = PASS
S1.2 canonical completeness = BLOCKED by single-bank semantic value capacity
S1.3 Def/Use = BLOCKED pending value namespace banking
VALUE_CAPACITY=365
BINDING_VALUE_ID_RANGE=0..298
CONSTANT_VALUE_ID_RANGE=299..364
RESULT_VALUE_ID_RANGE=NONE_AVAILABLE
```

## Architectural facts

- `tryte` is bounded to `[-364,364]`.
- S3 arrays/memory objects therefore have maximum length 365 (`0..364`).
- A single array larger than 365 is NOT an authorized solution.
- S3IR2 value IDs use module-monotonic global logical IDs, not per-function resets.
- The canonical Stage1 already uses explicit banked storage for other large record domains.

Therefore resolve capacity with explicit banks/pages of <=365 records while keeping logical IDs as global `i64` values.

Before mutation, obtain exact current canonical required value count from the hosted semantic IR reference. Hosted output is architecture/oracle evidence only. Then choose/prove minimal bank capacity, implement it, and re-run until required values fit and the canonical typed-value lane is complete without truncation.

Only after that gate may ordinary S1.3 instruction def/use resume.

## Locked

No per-function value-ID reset.
No single S3 array >365.
No arbitrary capacity increase without exact required-count evidence.
No weakening completeness/fail-closed tests.
No S1.4 calls, S1.5 terminators, S1.6 serialization, S1.7 emitter, SELF_EMIT, Stage2, Stage3, T4, or benchmark before the required gates.
No PR merge.
No force push.
No history rewrite.
No destructive cleanup/reset/restore of historical evidence worktrees.

## Shutdown override

The current user instruction supersedes the old overnight shutdown behavior.

```text
COMPUTER_SHUTDOWN_AUTHORIZED=NO
```

Do not execute shutdown, reboot, suspend, hibernate, `Stop-Computer`, `Restart-Computer`, `poweroff`, or equivalent commands.

## Evidence policy

```text
missing evidence = NOT_PROVABLE / NOT_RUN
hosted oracle = NOT native Stage1 proof
PASS = exact concrete evidence only
```
