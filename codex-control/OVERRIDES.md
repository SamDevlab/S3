# Live overrides

CONTROL_REVISION: 32

## CLEAN WORKTREE + CLASSIFICATION ONLY

Revision 31 preservation completed with no blocker.

Verified recovery package:

```text
C:\Users\samue\Downloads\S3\S3-PR268-Recovery-Rev31-20260827-214412
```

Verified facts:

```text
LOCAL_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
REMOTE_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
LEFT_RIGHT=0 0
TRACKED_MODIFIED=36
UNTRACKED=454
TRACKED_DIFF_PATCH_SHA256=0ffb5b361b70a89d16e6393117efd8d5b5bf028742e04bf3303d6297ddd388fd
SHA256_MANIFEST_ENTRIES=210
```

Critical recovery copies match originals:

```text
canonical Stage03-lineage = 739dc6ac16c2c79a4f3bff0b7ca2f40324171b3ad155f7a6265747d441cb5758
expression lowering = ff047a880b871d6428e2f33198db09d9b5c416b940df8bfe4d96867031439858
semantic stream = b2ee279dbb11358a0c5b9774e08e9217f4c904a9bb39825a71ad8362362e4d5c
```

## Authorized now

Read `codex-control/RECOVERY_REV32_CLEAN_WORKTREE_CLASSIFICATION.md`.

1. Create a NEW detached clean worktree outside the dirty checkout at exact commit `d67da9e...`.
2. Verify the new worktree has empty `git status --short`.
3. Leave the original dirty worktree untouched.
4. Read the Rev31 recovery manifests and dirty worktree read-only.
5. Classify relevant source/test/tool/report artifacts into KEEP / QUARANTINE / REGENERABLE / UNKNOWN categories defined by revision 32.
6. Write classification manifests outside both worktrees.
7. Return classification counts and STOP.

## Forbidden

No source changes in either worktree.
No patch apply or file copy into clean worktree.
No cleanup of dirty worktree.
No tests/builds/probes.
No commit/push.
No pull/rebase/merge.
No reset/restore/clean of original.
No canonical promotion/mutation.
No semantic-stage advance.
No SELF_EMIT/Stage2/Stage3/T4/benchmark/merge.

## Authorization boundary

Create detached clean worktree = YES
Classification outside worktrees = YES
Original dirty worktree mutation = NO
Clean source mutation = NO
Reapply work = NO
Cleanup = NO
Build/test = NO
Commit/push = NO
Semantic resume = NOT YET
