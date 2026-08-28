# Codex fast path — recovery/classification

Read `CURRENT.json`, `OVERRIDES.md`, and `RECOVERY_REV32_CLEAN_WORKTREE_CLASSIFICATION.md` first.

## REVISION 32 — CLEAN WORKTREE + CLASSIFICATION ONLY

Revision 31 preservation is complete and verified.

```text
HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
DIRTY_TRACKED=36
DIRTY_UNTRACKED=454
RECOVERY_PACKAGE=C:\Users\samue\Downloads\S3\S3-PR268-Recovery-Rev31-20260827-214412
```

## Do this now

```text
1. create NEW detached worktree at exact d67da9e outside dirty checkout
2. verify clean worktree status is empty
3. do NOT modify original dirty worktree
4. do NOT apply/copy any preserved changes yet
5. classify preserved relevant artifacts into:
   KEEP_STAGE1_CORE
   KEEP_EXPRESSION_LOWERING
   KEEP_CALLS_STAGE1
   KEEP_ORACLE_AND_CONFORMANCE
   QUARANTINE_OLD_COMPACTION_CAPACITY
   QUARANTINE_HISTORICAL_REPORTS
   REGENERABLE_ARTIFACTS
   UNKNOWN_REVIEW_REQUIRED
6. write classification manifests outside both worktrees
7. return checkpoint
8. STOP
```

Critical artifacts that must be classified explicitly:

```text
selfhost/compiler/s3c_stage1.s3
.artifacts/s3c_stage1_expression_lowering_v2.s3
selfhost/compiler/stage1_semantic_stream_v2.s3
bootstrap/s3/codegen.py
bootstrap/s3/initialization.py
bootstrap/s3/optimizer.py
all Stage1 semantic/codegen/call/expression-lowering tools/tests
```

## Return

```text
PAIRING_CLASSIFICATION_BEGIN
CONTROL_REVISION=32
ORIGINAL_DIRTY_WORKTREE_PATH=
ORIGINAL_DIRTY_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
ORIGINAL_DIRTY_STATUS_UNCHANGED=
CLEAN_WORKTREE_PATH=
CLEAN_WORKTREE_OUTSIDE_DIRTY=YES
CLEAN_WORKTREE_HEAD=
CLEAN_WORKTREE_STATUS_EMPTY=
KEEP_STAGE1_CORE_COUNT=
KEEP_EXPRESSION_LOWERING_COUNT=
KEEP_CALLS_STAGE1_COUNT=
KEEP_ORACLE_AND_CONFORMANCE_COUNT=
QUARANTINE_OLD_COMPACTION_CAPACITY_COUNT=
QUARANTINE_HISTORICAL_REPORTS_COUNT=
REGENERABLE_ARTIFACTS_COUNT=
UNKNOWN_REVIEW_REQUIRED_COUNT=
CLASSIFICATION_FILES=
CANONICAL_STAGE03_LINEAGE_CLASSIFICATION=
EXPRESSION_LOWERING_CLASSIFICATION=
SEMANTIC_STREAM_CLASSIFICATION=
PATCH_OR_COPY_APPLIED_TO_CLEAN_WORKTREE=NO
NEW_TEST=NO
NEW_BUILD=NO
NEW_COMMIT=NO
NEW_PUSH=NO
CLEANUP_OR_DELETION=NO
SEMANTIC_STAGE_ADVANCED=NO
FIRST_CLASSIFICATION_BLOCKER=
PAIRING_CLASSIFICATION_END
```

## Locked

No source mutation.
No patch/copy reapplication.
No cleanup.
No tests/builds.
No commit/push.
No canonical promotion.
No SELF_EMIT/Stage2/Stage3/T4/benchmark/merge.
