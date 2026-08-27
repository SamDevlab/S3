# Stage05 command card — Codex fast path

Use this file only after reading `CURRENT.json` and `OVERRIDES.md`.

## REVISION 25 — RECOVERY ONLY

The active Stage05 campaign is paused because context compaction continued into the old pre-IR/compaction route despite revision-23/24 stops.

Latest supplied transcript reports:

```text
E0_BUILD_RC=0
E1_BUILD=COMPLETED
2x2 matrix native runs=4
all rc=2
E0(S0)=E0(S1)=1460/305/1213
E1(S0)=E1(S1)=1097/329/1213
common overflow offset=41502
E0H histogram build=STARTED
```

These are drift/recovery facts, not Stage05 promotion evidence.

Read:

```text
codex-control/RECOVERY_REV25_STOP_AFTER_INFLIGHT_E0H.md
```

## Do this now

```text
if exact E0H process is already running:
    let that exact PID finish
else:
    do not start/restart E0H

then:
    DO NOT execute E0H
    DO NOT start E1H
    DO NOT run any matrix/fixture/histogram command
    capture recovery snapshot
    return PAIRING_RECOVERY block
    STOP
```

No new compiler build.
No new instrumentation.
No cleanup/deletion of worktree files during the snapshot.

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
CONTROL_REVISION=25
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
E0_BUILD_RC=0
E1_BUILD_RC=
MATRIX_RUN_COUNT=4
MATRIX_E0_S0=
MATRIX_E0_S1=
MATRIX_E1_S0=
MATRIX_E1_S1=
MATRIX_COMMON_OVERFLOW_OFFSET=
HISTOGRAM_TEMP_FILES=
E0H_STATUS=
E0H_BUILD_RC=
E0H_OUTPUT_SHA256=
E0H_EXECUTED=NO
E1H_STARTED=NO
NEW_BUILD_STARTED_AFTER_REV25=NO
GUEST_FREE=
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
No matrix/fixture/histogram execution.
