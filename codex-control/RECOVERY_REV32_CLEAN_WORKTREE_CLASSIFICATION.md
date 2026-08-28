# Recovery revision 32 — clean worktree + classification only

Revision 31 preservation completed successfully.

## Proven preservation

```text
LOCAL_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
REMOTE_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
LEFT_RIGHT=0 0
RECOVERY_PACKAGE=C:\Users\samue\Downloads\S3\S3-PR268-Recovery-Rev31-20260827-214412
TRACKED_DIFF_PATCH_SHA256=0ffb5b361b70a89d16e6393117efd8d5b5bf028742e04bf3303d6297ddd388fd
TRACKED_MODIFIED=36
UNTRACKED=454
SHA256_MANIFEST_ENTRIES=210
WORKTREE_STATUS_CHANGED_BY_EXPORT=NO
```

Critical copies verified equal:

```text
canonical Stage03-lineage sha256=739dc6ac16c2c79a4f3bff0b7ca2f40324171b3ad155f7a6265747d441cb5758
expression lowering sha256=ff047a880b871d6428e2f33198db09d9b5c416b940df8bfe4d96867031439858
semantic stream sha256=b2ee279dbb11358a0c5b9774e08e9217f4c904a9bb39825a71ad8362362e4d5c
```

## Authorized action

Create a NEW clean detached Git worktree outside the dirty checkout at exact commit:

```text
d67da9ea7dc8b83b0b80adb681011717eebec616
```

The original dirty worktree must remain untouched and preserved.

After creating the clean worktree, verify:

```text
HEAD=d67da9e...
git status --short = empty
```

Then perform classification only. Do not copy/reapply source changes yet.

Read the revision-31 recovery package manifests and the original dirty worktree read-only. Classify relevant changed/untracked files into:

```text
KEEP_STAGE1_CORE
KEEP_EXPRESSION_LOWERING
KEEP_CALLS_STAGE1
KEEP_ORACLE_AND_CONFORMANCE
QUARANTINE_OLD_COMPACTION_CAPACITY
QUARANTINE_HISTORICAL_REPORTS
REGENERABLE_ARTIFACTS
UNKNOWN_REVIEW_REQUIRED
```

Classification should prioritize source/test/tool artifacts, not opaque build outputs.

For each KEEP/UNKNOWN path, record:

- tracked/untracked state;
- SHA256;
- bytes;
- semantic purpose inferred from path/content/diff;
- whether it differs from clean HEAD;
- whether it appears required for Stage1 resumption.

At minimum inspect these critical artifacts:

```text
selfhost/compiler/s3c_stage1.s3
.artifacts/s3c_stage1_expression_lowering_v2.s3
selfhost/compiler/stage1_semantic_stream_v2.s3
bootstrap/s3/codegen.py
bootstrap/s3/initialization.py
bootstrap/s3/optimizer.py
all modified/untracked Stage1 semantic/codegen/call/expression-lowering tools/tests
```

Write classification output only OUTSIDE both Git worktrees, preferably inside the existing Rev31 recovery package as:

```text
rev32-classification.txt
rev32-keep-manifest.txt
rev32-quarantine-manifest.txt
rev32-regenerable-manifest.txt
rev32-unknown-manifest.txt
```

## Forbidden

No changes to original dirty worktree.
No source changes in clean worktree.
No applying patches/copies yet.
No tests/builds/probes.
No commit/push.
No reset/restore/clean of original.
No canonical promotion.
No semantic stage advance.
No SELF_EMIT/Stage2/Stage3/T4/benchmark/merge.

The only Git mutation authorized is creation of the new detached clean worktree at exact d67da9e.

Return clean worktree path/status and classification counts, then STOP.
