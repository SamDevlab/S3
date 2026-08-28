# Stage05 command card — Codex fast path

Use this file only after reading `CURRENT.json` and `OVERRIDES.md`.

## REVISION 29 — STALE-CONTEXT FIREWALL / SNAPSHOT ONLY

Current control is **NOT Stage03**.

```text
CONTROL_REVISION=29
ACTIVE_STAGE=05_CALLS_ARRAYS_S3
REMOTE_PR268_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
```

Historical summaries such as:

```text
CONTROL_REVISION=3
ACTIVE_STAGE=03_PASS1_BINDINGS
HEAD=800a3ab / 326d42f era
```

are stale. `reports/selfhost/stage1/PASS1_BINDINGS_CANDIDATE_20260827.md` is historical evidence only.

## Stale-context rule

```text
if reported CONTROL_REVISION < 29:
    STALE_CONTEXT
    do not regress stage
    do not execute its NEXT

if reported ACTIVE_STAGE=03 while CURRENT.json says Stage05:
    STALE_CONTEXT

only a newer CURRENT.json may supersede revision 29
```

A local editor artifact `stage1_expression_lowering_v2.s3` with about +1410 lines was reported. It is not in the remote PR delta. Treat it as `LOCAL_UNRECONCILED_ARTIFACT` until the snapshot proves exact status/hash/diff.

## Do this now

```text
NO edits
NO tests
NO builds
NO cleanup
NO commit
NO push
NO force-push
NO revert

capture LOCAL post-push worktree state
include stage1_expression_lowering_v2.s3 status/hash/diff if present
return revision-29 recovery block
STOP
```

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

## Return

```text
PAIRING_RECOVERY_BEGIN
CONTROL_REVISION=29
WORKTREE_HEAD=
WORKTREE_BRANCH=
REMOTE_PR268_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
LOCAL_EQUALS_REMOTE_HEAD=
GIT_STATUS_SHORT=
CHANGED_FILE_COUNT=
CHANGED_FILES=
UNTRACKED_FILES=
PER_FILE_DIFF_STAT=
STAGE05_OWNED_CHANGED_FILES=
OLD_COMPACTION_DRIFT_CHANGED_FILES=
CANONICAL_OR_OTHER_CHANGED_FILES=
CANONICAL_LOCAL_SHA256=
CANONICAL_LOCAL_BYTES=
CANONICAL_HEAD_SHA256=
CANONICAL_HEAD_BYTES=
CANONICAL_DIFF_PRESENT=
CANONICAL_DIFF_PATCH_SAVED=
STAGE05_CANDIDATE_SHA256=
STAGE05_TRANSFORM_SHA256=
STAGE05_TEMP_TELEMETRY_PRESENT=
EXPRESSION_LOWERING_ARTIFACT_PRESENT=
EXPRESSION_LOWERING_ARTIFACT_PATH=
EXPRESSION_LOWERING_ARTIFACT_TRACKED_STATE=
EXPRESSION_LOWERING_ARTIFACT_SHA256=
EXPRESSION_LOWERING_ARTIFACT_BYTES=
EXPRESSION_LOWERING_ARTIFACT_DIFF_STAT=
REMOTE_CONTAINED_COMPACTION_COMMITS=6e6b837,8c02802,d67da9e
REMOTE_CANONICAL_PATH_CHANGED=NO
REMOTE_WORKFLOW_STATUS=FAILURE_OBSERVED_CAUSE_NOT_ATTRIBUTED
NEW_EDIT_AFTER_REV29=NO
NEW_TEST_AFTER_REV29=NO
NEW_BUILD_AFTER_REV29=NO
NEW_COMMIT_AFTER_REV29=NO
NEW_PUSH_AFTER_REV29=NO
CANONICAL_RESTORED_OR_REVERTED=NO
T4_EXECUTED=NO
BENCHMARK_EXECUTED=NO
FIRST_RECOVERY_BLOCKER=
PAIRING_RECOVERY_END
```

## Locked

No arrays.
No foreign calls.
No capacity work.
No Stage06.
No canonical mutation/restore/revert.
No implementation commit/push.
No SELF_EMIT.
No Stage2/Stage3/T4.
No benchmark.
No old compaction continuation.
No regression to Stage03 from stale context.
