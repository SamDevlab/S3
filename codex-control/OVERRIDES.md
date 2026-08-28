# Live overrides

CONTROL_REVISION: 29

## STALE-CONTEXT FIREWALL + POST-PUSH SNAPSHOT ONLY

Historical Codex summaries resurfaced reporting:

```text
CONTROL_REVISION=3
ACTIVE_STAGE=03_PASS1_BINDINGS
HEAD around 800a3ab / 326d42f
```

Those are historical checkpoints, not current control.

The file:

```text
reports/selfhost/stage1/PASS1_BINDINGS_CANDIDATE_20260827.md
```

is valid Stage03 evidence but explicitly records `CONTROL_REVISION=3` and `ACTIVE_STAGE=03_PASS1_BINDINGS`. It must never override `codex-control/CURRENT.json`.

Current authoritative remote state remains:

```text
CONTROL_REVISION=29
ACTIVE_STAGE=05_CALLS_ARRAYS_S3
PR268_HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
PR268_STATE=OPEN_DRAFT_MERGEABLE_NOT_MERGED
```

## Hard stale-context rule

```text
IF any compacted summary / historical report says CONTROL_REVISION < 29:
    classify STALE_CONTEXT
    do not regress stage
    do not execute its NEXT instruction

IF it says ACTIVE_STAGE=03 while CURRENT.json says Stage05:
    classify STALE_CONTEXT

ONLY a newer codex-control/CURRENT.json may supersede revision 29.
```

The separately reported local edit:

```text
stage1_expression_lowering_v2.s3
+1410 lines reported in editor
```

is not present as a changed path in the remote PR #268 delta. Treat it as:

```text
LOCAL_UNRECONCILED_ARTIFACT
```

until the local snapshot reports exact path, tracked/untracked state, SHA256, bytes and diff stat. Do not delete, restore, build, test, commit or push it.

## Do this now

No more edits.
No tests.
No builds.
No cleanup.
No commit.
No push.
No force-push.
No revert.

Capture the LOCAL post-push state only, including the expression-lowering artifact if present:

1. exact local HEAD and branch;
2. equality with remote `d67da9e...`;
3. exact `git status --short`;
4. changed and untracked lists;
5. per-file diff stats;
6. classify Stage05-owned vs old-compaction vs canonical/other;
7. canonical local-vs-HEAD hash/bytes and saved patch provenance;
8. Stage05 candidate/transform hashes and telemetry state;
9. `stage1_expression_lowering_v2.s3` path/status/SHA/bytes/diff if present;
10. return the revision-29 recovery block;
11. STOP.

## Preserve Stage05 evidence

```text
one-arg internal call -> structural good / Z3
ordered multi-arg internal call -> recovered to Z3
unresolved callee -> fail-closed
nested call with representable inner result -> pass
nested a + 1 fixture -> expression-lowering limitation reproduced without call
```

Preserve the two comma/cursor repairs and the Stage05-consumed-token legacy-dispatch guard.

## Forbidden

```text
git reset --hard
git clean
git checkout -- <path>
git restore <path>
git push --force
```

No implementation commit or push.
No canonical mutation/restore/revert.
No arrays, foreign calls, capacity work, Stage06+.
No SELF_EMIT, Stage2, Stage3, T4 or benchmark.

## Authorization boundary

Historical Stage03 checkpoint = EVIDENCE_ONLY
Stage regression from stale summary = NO
New native build = NO
New test execution = NO
Source/report/qualifier edit = NO
Cleanup = NO
Implementation commit = NO
Implementation push = NO
Force reset/revert remote commits = NO
Canonical mutation = NO
Canonical restore/revert = NO
Arrays = NO
Foreign calls = NO
Stage06 = NO
SELF_EMIT = NO
Stage2 = NO
Stage3 = NO
T4 = NO
Benchmark = NO
