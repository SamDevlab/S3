# Stage05 command card — Codex fast path

Use this file only after reading `CURRENT.json` and `OVERRIDES.md`.

## REVISION 24 — RECOVERY ONLY

The Stage05 campaign is temporarily paused because context compaction drifted into the old pre-IR/compaction 2x2 route.

Latest supplied transcript reports:

```text
E0_BUILD_RC=0
E1_BUILD=STARTED
GUEST_FREE_BEFORE=831 MB
GUEST_FREE_AFTER_CONTROLLED_TMP_CLEANUP=3.9 GB
```

These are recovery facts, not Stage05 promotion evidence.

Read:

```text
codex-control/RECOVERY_REV24_STOP_AFTER_INFLIGHT_E1.md
```

## Do this now

```text
if exact E1 process is already running:
    let that exact PID finish
else:
    do not start/restart E1

then:
    run ZERO 2x2 matrix executions
    capture recovery snapshot
    return PAIRING_RECOVERY block
    STOP
```

No new compiler build.
No E0 restart.
No E1 restart.
No matrix execution.

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
CONTROL_REVISION=24
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
E0_BUILD_RC=
E0_OUTPUT_SHA256=
E1_STATUS=
E1_BUILD_RC=
E1_OUTPUT_SHA256=
MATRIX_EXECUTIONS_AFTER_REV24=0
GUEST_FREE_AFTER_E1=
NEW_BUILD_STARTED_AFTER_REV24=NO
CANONICAL_RESTORED_OR_REVERTED=NO
IMPLEMENTATION_COMMIT_CREATED=NO
T4_EXECUTED=NO
BENCHMARK_EXECUTED=NO
FIRST_RECOVERY_BLOCKER=
PAIRING_RECOVERY_END
```

## Locked until a newer revision

No arrays.
No foreign calls.
No capacity work.
No Stage06.
No canonical mutation/restore/revert.
No implementation commit.
No SELF_EMIT.
No Stage2/Stage3/T4.
No benchmark.
