# Revision 23 — worktree reconciliation after context drift

This is a temporary recovery stop, not a rollback of valid Stage05 progress.

## Why this stop exists

The supplied Codex transcript contains two distinct phases after context compaction:

1. valid continuation of the paired Stage05 call campaign;
2. later work from an older PR #268/pre-IR/compaction route that was not authorized by the live paired control.

Do not mix evidence from those routes.

## Valid Stage05 evidence to preserve

The latest supplied transcript reports all of the following before the route drift:

- the consumed-token legacy-dispatch guard was applied on a clean candidate;
- ordered multi-argument internal calls recovered from `Z0` to `Z3`;
- unresolved callee remains fail-closed;
- nested calls whose inner result is already representable pass;
- the remaining failing nested fixture uses arithmetic such as `a + 1` in the inner function;
- that arithmetic limitation reproduces even without a call, so it is an expression-lowering limitation and must not be mislabeled as a nested-call failure.

Do not discard the two prior comma/cursor fixes or the consumed-token guard.

## Out-of-scope work observed after context compaction

The transcript then reports work that is outside the revision-22 authorization boundary:

- beginning array-route inspection before the internal-call strict gate was closed;
- switching to an older PR #268/pre-IR/compaction 2x2 experiment;
- preparing E0/E1 cross-build work;
- observing local changes in the canonical Stage1 source even though canonical mutation was not authorized by the paired control;
- a native build failing because the Linux guest ran out of disk space.

No result from that out-of-scope route may be promoted into Stage05 evidence or a later-stage PASS.

## EMERGENCY RECONCILIATION STOP

Until a recovery checkpoint is returned:

- do not start a new native compiler build;
- do not start E1 or another 2x2 cross-build;
- do not run T4;
- do not run benchmarks;
- do not edit arrays;
- do not edit foreign-call lowering;
- do not edit capacity planning;
- do not mutate or restore the canonical Stage1 source yet;
- do not commit implementation work;
- do not merge any PR.

If an already-running process has already reached terminal state, record that terminal state only. Do not replace it with a new run.

## Recovery snapshot — no destructive worktree action

Capture and return:

```text
WORKTREE_HEAD=<git rev-parse HEAD>
WORKTREE_BRANCH=<current branch>
REMOTE_PR268_HEAD=326d42f8a2623ced5a2151d6daaf2d67743faca8
GIT_STATUS_SHORT=<preserve complete output separately>
CHANGED_FILES=<git diff --name-status plus untracked summary>

CANONICAL_PATH=selfhost/compiler/s3c_stage1.s3
CANONICAL_LOCAL_SHA256=<sha256 of current worktree bytes>
CANONICAL_LOCAL_BYTES=<bytes>
CANONICAL_HEAD_SHA256=<sha256 of HEAD blob bytes>
CANONICAL_HEAD_BYTES=<bytes>
CANONICAL_DIFF_PRESENT=YES/NO
CANONICAL_DIFF_PATCH_SAVED=<path or NOT_SAVED>

STAGE05_CANDIDATE_SHA256=<current clean candidate sha or NOT_RECORDED>
STAGE05_TRANSFORM_SHA256=<current transform/generator sha or NOT_RECORDED>
STAGE05_TEMP_TELEMETRY_PRESENT=YES/NO

GUEST_ROOT_FREE=<df result>
GUEST_TMP_FREE=<df result if separate>
OUT_OF_SPACE_BUILD=<which command/artifact, or NOT_RECORDED>
TEMP_FILES_CREATED_BY_CURRENT_MATRIX=<paths only>
```

Before any restore/revert, save the canonical diff to a temporary patch outside the repository if possible. The purpose is provenance, not promotion.

## Disk cleanup authorization

Disk cleanup is allowed only for disposable artifacts created by the current diagnostic/cross-build attempts under temporary locations such as `/tmp`.

Allowed:

- failed temporary assembly/output files created by the current E0/E1 or Stage05 diagnostic builds;
- temporary copied source/candidate files under `/tmp` that can be regenerated from the preserved worktree;
- stale `/tmp` outputs clearly attributable to the current campaign.

Not allowed during recovery:

- deleting repository files;
- `git clean`;
- `git reset --hard`;
- checkout/restore of canonical source;
- deleting untracked worktree files without first listing them;
- deleting caches or toolchains merely to create space unless a later control revision explicitly authorizes it.

After cleanup, record only `df -h`/free-space evidence. Do not start a new build yet.

## Stage05 resumption point after reconciliation

The intended resumption point is not arrays and not the old compaction route.

It is:

```text
multi-arg internal call = reported Z3
one-arg internal call = reported structural good / Z3
unresolved callee = reported fail-closed
nested call with representable inner result = reported pass
arithmetic-inner nested fixture = expression-lowering dependency, not call blocker
```

After the recovery checkpoint is reviewed, a later control revision will decide whether to:

1. run the stage-local strict conformance gate immediately on the clean one-arg/multiarg candidate;
2. inspect the Stage05 S3 completeness predicate if strict passes but `Z3` persists;
3. defer the unrelated arithmetic-expression dependency to its owning stage/regression lane;
4. only then decide when arrays/foreign calls may unlock.

## Recovery checkpoint

```text
PAIRING_RECOVERY_BEGIN
CONTROL_REVISION=23
WORKTREE_HEAD=
WORKTREE_BRANCH=
REMOTE_PR268_HEAD=326d42f8a2623ced5a2151d6daaf2d67743faca8
CANONICAL_LOCAL_SHA256=
CANONICAL_HEAD_SHA256=
CANONICAL_DIFF_PRESENT=
CANONICAL_DIFF_PATCH_SAVED=
STAGE05_CANDIDATE_SHA256=
STAGE05_TRANSFORM_SHA256=
STAGE05_TEMP_TELEMETRY_PRESENT=
OUT_OF_SCOPE_2X2_FILES_PRESENT=
GUEST_FREE_BEFORE=
GUEST_FREE_AFTER=
OUT_OF_SPACE_ARTIFACT=
NEW_BUILD_STARTED_AFTER_REV23=NO
CANONICAL_RESTORED_OR_REVERTED=NO
IMPLEMENTATION_COMMIT_CREATED=NO
T4_EXECUTED=NO
BENCHMARK_EXECUTED=NO
FIRST_RECOVERY_BLOCKER=<one blocker or NONE>
PAIRING_RECOVERY_END
```
