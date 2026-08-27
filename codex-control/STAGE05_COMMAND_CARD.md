# Stage05 command card — Codex fast path

Use this file only after reading `CURRENT.json` and `OVERRIDES.md`.

## REVISION 27 — SNAPSHOT ONLY

The active Stage05 campaign is paused because context compaction repeatedly resumed the old pre-IR/compaction route.

Latest supplied local state:

```text
qualifier edited again after revision 26
planned next step = add 2 tests + run focused compaction/lane suite
worktree reported = 12 files changed
```

Do **not** perform that planned next step.

The qualifier edit is preserved as unvalidated local work. Its intended contract may be sound, but it is not authorized for further validation during recovery.

## Do this now

```text
NO new test files
NO test execution
NO source/report/qualifier edits
NO new native build
NO matrix/fixture/histogram commands
NO cleanup/deletion

if exact native PID already existed before first reading rev27:
    let only that PID reach terminal state
    do not execute its output

then:
    READ-ONLY SNAPSHOT
    return recovery block
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

## Return this checkpoint

```text
PAIRING_RECOVERY_BEGIN
CONTROL_REVISION=27
WORKTREE_HEAD=
WORKTREE_BRANCH=
REMOTE_PR268_HEAD=326d42f8a2623ced5a2151d6daaf2d67743faca8

GIT_STATUS_SHORT=
CHANGED_FILE_COUNT=
CHANGED_FILES=
UNTRACKED_FILES=
PER_FILE_DIFF_STAT=

STAGE05_OWNED_CHANGED_FILES=
OLD_COMPACTION_DRIFT_CHANGED_FILES=
OTHER_UNCLASSIFIED_CHANGED_FILES=

CANONICAL_LOCAL_SHA256=
CANONICAL_LOCAL_BYTES=
CANONICAL_HEAD_SHA256=
CANONICAL_HEAD_BYTES=
CANONICAL_DIFF_PRESENT=
CANONICAL_DIFF_PATCH_SAVED=

STAGE05_CANDIDATE_SHA256=
STAGE05_TRANSFORM_SHA256=
STAGE05_TEMP_TELEMETRY_PRESENT=

LATEST_QUALIFIER_FILE=
LATEST_QUALIFIER_DIFF_SUMMARY=
PLANNED_TEST_FILES_CREATED_AFTER_REV27=NO
FOCUSED_COMPACTION_LANE_SUITE_EXECUTED_AFTER_REV27=NO

EXISTING_NATIVE_PID_STATUS=
TMP_COMPACTION_HISTOGRAM_ARTIFACTS=
GUEST_FREE=

NEW_BUILD_STARTED_AFTER_REV27=NO
NEW_TEST_EXECUTED_AFTER_REV27=NO
SOURCE_OR_REPORT_EDIT_AFTER_REV27=NO
CLEANUP_OR_DELETION_AFTER_REV27=NO
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
No old compaction validation.
