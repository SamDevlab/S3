# Stage05 command card — Codex fast path

Use this file only after reading `CURRENT.json` and `OVERRIDES.md`.

## REVISION 26 — READ-ONLY RECOVERY

The Stage05 campaign is paused because context compaction repeatedly resumed the old pre-IR/compaction route.

Latest supplied drift evidence:

```text
E0/E1 completed
4 matrix runs rc=2
E0(S0)=E0(S1)=1460/305/1213
E1(S0)=E1(S1)=1097/329/1213
boundary=41502
E0H completed
E1H started
histogram interpretation says opcode 5 is the only observable changed lane
first packed-token spill literal 1000000000000 at 41502
removed assignments at 88492 and 88540
report/qualifier files edited locally after compaction
```

These are recovery facts only. Do not continue that route.

Read:

```text
codex-control/RECOVERY_REV26_READ_ONLY_SNAPSHOT.md
```

## Do this now

```text
if any exact native PID that was already running before revision 26 is still alive:
    let that exact PID terminate
    do not execute its output
else:
    start nothing

then:
    READ-ONLY SNAPSHOT ONLY
    return PAIRING_RECOVERY block
    STOP
```

No new compiler build.
No new test execution.
No matrix/fixture/histogram command.
No source/report/qualifier edit.
No cleanup/deletion during the snapshot.

## Preserve valid Stage05 progress

```text
one-arg = structural good / Z3
multi-arg = recovered to Z3
unresolved = fail-closed
nested with representable result = pass
nested a + 1 failure = expression-lowering dependency reproduced without call
```

Preserve:

- comma double-advance repair;
- comma revisit / `has_arg=0` repair;
- Stage05-consumed-token legacy-dispatch guard.

## Recovery fields

Return:

```text
PAIRING_RECOVERY_BEGIN
CONTROL_REVISION=26
WORKTREE_HEAD=
WORKTREE_BRANCH=
REMOTE_PR268_HEAD=326d42f8a2623ced5a2151d6daaf2d67743faca8
GIT_STATUS_SHORT=
CHANGED_FILES=
UNTRACKED_FILES=

CANONICAL_LOCAL_SHA256=
CANONICAL_LOCAL_BYTES=
CANONICAL_HEAD_SHA256=
CANONICAL_HEAD_BYTES=
CANONICAL_DIFF_PRESENT=
CANONICAL_DIFF_PATCH_SAVED=

STAGE05_CANDIDATE_SHA256=
STAGE05_TRANSFORM_SHA256=
STAGE05_TEMP_TELEMETRY_PRESENT=

DRIFT_MODIFIED_REPORT_FILES=
DRIFT_MODIFIED_QUALIFIER_FILES=

E0_BUILD_RC=0
E1_BUILD_RC=
E0_OUTPUT_SHA256=
E1_OUTPUT_SHA256=

MATRIX_RUN_COUNT=4
MATRIX_E0_S0=1460/305/1213
MATRIX_E0_S1=1460/305/1213
MATRIX_E1_S0=1097/329/1213
MATRIX_E1_S1=1097/329/1213
MATRIX_COMMON_OVERFLOW_OFFSET=41502

E0H_STATUS=
E0H_BUILD_RC=
E0H_OUTPUT_SHA256=
E0H_EXECUTED=
E1H_STATUS=
E1H_BUILD_RC=
E1H_OUTPUT_SHA256=
E1H_EXECUTED=

HISTOGRAM_ALREADY_OBSERVED=
HISTOGRAM_OPCODE5_ONLY_DIFFERENCE_REPORTED=YES
FIRST_PACKED_TOKEN_SPILL_LITERAL=1000000000000
FIRST_PACKED_TOKEN_SPILL_OFFSET=41502
REMOVED_ASSIGNMENT_OFFSETS=88492,88540
TMP_COMPACTION_HISTOGRAM_ARTIFACTS=
GUEST_FREE=

NEW_BUILD_STARTED_AFTER_REV26=NO
NEW_TEST_EXECUTED_AFTER_REV26=NO
SOURCE_OR_REPORT_EDIT_AFTER_REV26=NO
CANONICAL_RESTORED_OR_REVERTED=NO
IMPLEMENTATION_COMMIT_CREATED=NO
T4_EXECUTED=NO
BENCHMARK_EXECUTED=NO
FIRST_RECOVERY_BLOCKER=
PAIRING_RECOVERY_END
```

## Locked until newer revision

No arrays.
No foreign calls.
No capacity work.
No Stage06.
No canonical mutation/restore/revert.
No implementation commit.
No SELF_EMIT.
No Stage2/Stage3/T4.
No benchmark.
No old compaction work.
