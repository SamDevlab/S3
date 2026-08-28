# Codex fast path — recovery/preservation

Read `CURRENT.json` and `OVERRIDES.md` first.

## REVISION 31 — DIRTY WORKTREE PRESERVATION

Reconciliation is complete:

```text
LOCAL_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
REMOTE_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
LEFT_RIGHT=0 0
TRACKED_MODIFIED=36
UNTRACKED=454
```

The problem is not branch divergence. The problem is a large uncommitted worktree.

Important preserved artifacts:

```text
canonical local:
  selfhost/compiler/s3c_stage1.s3
  sha256=739dc6ac16c2c79a4f3bff0b7ca2f40324171b3ad155f7a6265747d441cb5758
  bytes=211674
  classification=Stage03-lineage source

expression lowering:
  .artifacts/s3c_stage1_expression_lowering_v2.s3
  sha256=ff047a880b871d6428e2f33198db09d9b5c416b940df8bfe4d96867031439858
  bytes=222530
  tracked=NO
```

## Do this now

Create one recovery package OUTSIDE the repository, following:

```text
codex-control/RECOVERY_REV31_DIRTY_WORKTREE_PRESERVATION.md
```

Package must contain:

```text
git-status-short.txt
tracked-diff.patch            # git diff --binary HEAD
tracked-diff-stat.txt
changed-files.txt
untracked-files.txt
untracked-size-summary.txt
sha256-manifest.txt
canonical-local-stage03-lineage.s3
s3c_stage1_expression_lowering_v2.s3
stage1_semantic_stream_v2.s3  # if present
recovery-metadata.txt
```

Verify copied-source hashes against originals.

Do NOT modify the repository while creating the package.

## Return

```text
PAIRING_PRESERVATION_BEGIN
CONTROL_REVISION=31
LOCAL_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
REMOTE_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
LOCAL_REMOTE_LEFT_RIGHT=0 0
RECOVERY_PACKAGE_PATH=
RECOVERY_PACKAGE_OUTSIDE_REPOSITORY=YES
RECOVERY_PACKAGE_FILE_COUNT=
TRACKED_DIFF_PATCH_PRESENT=
TRACKED_DIFF_PATCH_SHA256=
CHANGED_FILES_MANIFEST_COUNT=
UNTRACKED_FILES_MANIFEST_COUNT=
SHA256_MANIFEST_ENTRY_COUNT=
UNTRACKED_TOTAL_BYTES=
UNTRACKED_TOP_LEVEL_SIZE_SUMMARY=
CANONICAL_COPY_PRESENT=
CANONICAL_ORIGINAL_SHA256=739dc6ac16c2c79a4f3bff0b7ca2f40324171b3ad155f7a6265747d441cb5758
CANONICAL_COPY_SHA256=
CANONICAL_COPY_MATCH=
EXPRESSION_LOWERING_COPY_PRESENT=
EXPRESSION_LOWERING_ORIGINAL_SHA256=ff047a880b871d6428e2f33198db09d9b5c416b940df8bfe4d96867031439858
EXPRESSION_LOWERING_COPY_SHA256=
EXPRESSION_LOWERING_COPY_MATCH=
SEMANTIC_STREAM_PRESENT=
SEMANTIC_STREAM_COPY_SHA256=
WORKTREE_STATUS_CHANGED_BY_EXPORT=NO
NEW_TEST=NO
NEW_BUILD=NO
NEW_COMMIT=NO
NEW_PUSH=NO
CLEANUP_OR_DELETION=NO
FIRST_PRESERVATION_BLOCKER=
PAIRING_PRESERVATION_END
```

Then STOP.

## Locked

No cleanup.
No semantic resume yet.
No source/report edits.
No tests/builds.
No commit/push.
No pull/rebase/merge.
No reset/restore/checkout/clean.
No canonical mutation.
No artifact regeneration.
No SELF_EMIT/Stage2/Stage3/T4/benchmark/merge.
