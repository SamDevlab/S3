# Recovery revision 31 — dirty worktree preservation

This checkpoint follows the revision-30 read-only reconciliation.

## Proven local/remote state

```text
LOCAL_BRANCH=feature/actual-stage1-compiler-seed-20260824
LOCAL_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
REMOTE_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
LOCAL_REMOTE_LEFT_RIGHT=0 0
TRACKED_MODIFIED=36
UNTRACKED=454
STAGED=0
```

The worktree is therefore not diverged by commits. It is dirty through uncommitted tracked/untracked content.

## Canonical provenance

Local canonical:

```text
PATH=selfhost/compiler/s3c_stage1.s3
LOCAL_SHA256=739dc6ac16c2c79a4f3bff0b7ca2f40324171b3ad155f7a6265747d441cb5758
LOCAL_BYTES=211674
HEAD_SHA256=ec6bef92782fe253f4b1c1390d90f95017670a3cbb65497eff9dba12a2e7623c
HEAD_BYTES=185508
DIFF_PRESENT=YES
```

The local SHA exactly matches the canonical SHA recorded by the Stage03 Pass1 checkpoint at commit `326d42f`, where `CANONICAL_SOURCE_MUTATED=NO` was reported. Treat the local canonical as preserved Stage03-lineage source, not random drift and not current-HEAD canonical.

Do not restore it, overwrite it, commit it, or use it as current canonical without a later explicit provenance decision.

## Expression-lowering artifact

```text
PATH=.artifacts/s3c_stage1_expression_lowering_v2.s3
TRACKED_STATE=UNTRACKED
SHA256=ff047a880b871d6428e2f33198db09d9b5c416b940df8bfe4d96867031439858
BYTES=222530
EXACT_BASENAME_stage1_expression_lowering_v2.s3=NOT_FOUND
```

Preserve this artifact. Do not delete, rebuild, promote, or overwrite it during recovery.

## Current classification

Tracked changes include Stage1 semantic/codegen/token-lane/capacity work plus reports and compaction-era files. Untracked content is dominated by `.artifacts/**`, reports, scratch-capacity stages, scratch files, and additional tools/tests/source artifacts.

Do not assume all 454 untracked files are disposable.

## Authorized action

Revision 31 authorizes preservation/export only, outside the repository working tree.

Create a recovery directory outside the repository, for example under the user's temp or Documents area, and write/copy only recovery evidence there.

Required recovery package:

1. `git-status-short.txt` — exact `git status --short`;
2. `tracked-diff.patch` — exact `git diff --binary HEAD`;
3. `tracked-diff-stat.txt` — exact `git diff --stat`;
4. `changed-files.txt` — exact tracked changed paths;
5. `untracked-files.txt` — exact untracked paths;
6. `untracked-size-summary.txt` — count/bytes grouped at least by top-level path;
7. `sha256-manifest.txt` — SHA256 + bytes for all tracked modified files and all untracked `.s3`, `.py`, `.json`, `.md`, `.txt` source/evidence files; do not hash huge opaque binaries unless inexpensive;
8. copy `selfhost/compiler/s3c_stage1.s3` as `canonical-local-stage03-lineage.s3`;
9. copy `.artifacts/s3c_stage1_expression_lowering_v2.s3` exactly;
10. copy `selfhost/compiler/stage1_semantic_stream_v2.s3` if present;
11. `recovery-metadata.txt` with branch, HEAD, remote HEAD, left/right count, and timestamps.

The recovery directory must be outside the repository so the worktree remains unchanged.

## Forbidden

No edits inside the repository.
No test/build/probe.
No commit/push/pull/rebase/merge.
No reset/restore/checkout/clean.
No deletion or cleanup.
No canonical mutation.
No artifact regeneration.
No semantic-stage advance.
No SELF_EMIT, Stage2, Stage3, T4, benchmark or merge.

After the external recovery package is created and verified, return its path, file list, manifest counts, hashes for the copied canonical/expression-lowering/semantic-stream artifacts, and STOP.
