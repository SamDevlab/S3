# Codex fast path — recovery/reconciliation

Read `CURRENT.json` and `OVERRIDES.md` first.

## REVISION 30 — LOCAL STAGE03 STOP CONFIRMED

The user confirmed the last supplied Stage03 output is exactly where the local Codex session stopped.

Do not classify it as stale.

Reported local stop:

```text
CONTROL_REVISION=3
ACTIVE_STAGE=03_PASS1_BINDINGS
commits around 800a3ab / 326d42f
Stage0 PASS
focused tests PASS
Linux native build PASS
trivial probe PASS
canonical not mutated
```

A later local editor state reported `stage1_expression_lowering_v2.s3` with approximately +1410 lines.

Current observed remote PR268 is later:

```text
REMOTE_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
OPEN / DRAFT / MERGEABLE / NOT MERGED
```

Therefore the next action is not Stage04 or Stage05 implementation. It is local/remote reconciliation.

## Do this now — READ ONLY

```text
1. git branch --show-current
2. git rev-parse HEAD
3. git status --short
4. git diff --stat
5. git diff --name-only
6. git ls-files --others --exclude-standard
7. git log --oneline --decorate -n 12
8. git fetch origin (read-only remote metadata only, no merge/rebase)
9. git rev-list --left-right --count HEAD...origin/feature/actual-stage1-compiler-seed-20260824
10. locate stage1_expression_lowering_v2.s3 if present and record path/tracked state/SHA256/bytes/diff stat
11. record canonical local-vs-HEAD SHA256/bytes
12. return block below
13. STOP
```

## Return

```text
PAIRING_RECONCILIATION_BEGIN
CONTROL_REVISION=30
LOCAL_STOP_CONFIRMED_STAGE=03_PASS1_BINDINGS
LOCAL_BRANCH=
LOCAL_HEAD=
REMOTE_PR268_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
LOCAL_REMOTE_LEFT_RIGHT_COUNT=
GIT_STATUS_SHORT=
CHANGED_FILES=
UNTRACKED_FILES=
PER_FILE_DIFF_STAT=
RECENT_LOCAL_LOG=
EXPRESSION_LOWERING_ARTIFACT_PRESENT=
EXPRESSION_LOWERING_ARTIFACT_PATH=
EXPRESSION_LOWERING_ARTIFACT_TRACKED_STATE=
EXPRESSION_LOWERING_ARTIFACT_SHA256=
EXPRESSION_LOWERING_ARTIFACT_BYTES=
EXPRESSION_LOWERING_ARTIFACT_DIFF_STAT=
CANONICAL_LOCAL_SHA256=
CANONICAL_LOCAL_BYTES=
CANONICAL_HEAD_SHA256=
CANONICAL_HEAD_BYTES=
CANONICAL_DIFF_PRESENT=
LOCAL_STAGE03_OWNED_CHANGED_FILES=
LATER_OR_UNCLASSIFIED_CHANGED_FILES=
NEW_EDIT_AFTER_REV30=NO
NEW_TEST_AFTER_REV30=NO
NEW_BUILD_AFTER_REV30=NO
NEW_COMMIT_AFTER_REV30=NO
NEW_PUSH_AFTER_REV30=NO
PULL_REBASE_MERGE_AFTER_REV30=NO
FIRST_RECONCILIATION_BLOCKER=
PAIRING_RECONCILIATION_END
```

## Locked

No semantic stage advance yet.
No edits/tests/builds.
No commit/push.
No pull/rebase/merge into the worktree.
No reset/restore/cleanup.
No canonical mutation.
No SELF_EMIT.
No Stage2/Stage3/T4.
No benchmark.
