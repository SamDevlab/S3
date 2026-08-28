# Live overrides

CONTROL_REVISION: 31

## DIRTY WORKTREE PRESERVATION — EXTERNAL EXPORT ONLY

Revision 30 reconciliation is complete.

```text
LOCAL_BRANCH=feature/actual-stage1-compiler-seed-20260824
LOCAL_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
REMOTE_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
LEFT_RIGHT=0 0
TRACKED_MODIFIED=36
UNTRACKED=454
STAGED=0
```

There is no commit divergence. The blocker is the dirty worktree.

## Canonical provenance

```text
LOCAL_CANONICAL_SHA256=739dc6ac16c2c79a4f3bff0b7ca2f40324171b3ad155f7a6265747d441cb5758
LOCAL_CANONICAL_BYTES=211674
HEAD_CANONICAL_SHA256=ec6bef92782fe253f4b1c1390d90f95017670a3cbb65497eff9dba12a2e7623c
HEAD_CANONICAL_BYTES=185508
DIFF_PRESENT=YES
```

`739dc6...` is the exact canonical SHA recorded by the Stage03 Pass1 checkpoint at commit `326d42f`, where canonical mutation was reported NO. Preserve the local file as Stage03-lineage source. Do not restore, overwrite, commit or promote it.

## Expression-lowering artifact

```text
PATH=.artifacts/s3c_stage1_expression_lowering_v2.s3
TRACKED=NO
SHA256=ff047a880b871d6428e2f33198db09d9b5c416b940df8bfe4d96867031439858
BYTES=222530
```

Preserve exactly. Do not rebuild or overwrite.

## Do this now

Read `codex-control/RECOVERY_REV31_DIRTY_WORKTREE_PRESERVATION.md`.

Create a recovery directory OUTSIDE the repository. The repository worktree must remain byte-for-byte unchanged.

Required package:

- exact `git status --short`;
- `git diff --binary HEAD` patch;
- diff stat;
- exact changed-file list;
- exact untracked-file list;
- untracked count/size summary by top-level path;
- SHA256+bytes manifest for all tracked modified files and untracked source/evidence files (`.s3`, `.py`, `.json`, `.md`, `.txt`);
- exact copy of local `selfhost/compiler/s3c_stage1.s3`;
- exact copy of `.artifacts/s3c_stage1_expression_lowering_v2.s3`;
- exact copy of `selfhost/compiler/stage1_semantic_stream_v2.s3` if present;
- metadata with local/remote HEAD and left/right count.

Verify copied-file hashes against originals.

Then return the revision-31 preservation checkpoint and STOP.

## Forbidden

No repository edit.
No tests/builds/probes.
No cleanup/deletion.
No commit/push.
No pull/rebase/merge.
No reset/restore/checkout/clean.
No canonical mutation.
No artifact regeneration.
No semantic stage advance.
No SELF_EMIT, Stage2, Stage3, T4, benchmark or merge.

## Authorization boundary

External recovery package = YES
Repository mutation = NO
Cleanup = NO
Build/test = NO
Commit/push = NO
Pull/rebase/merge = NO
Canonical restore/mutation = NO
Artifact regeneration = NO
Semantic resume stage = NOT YET DECIDED
