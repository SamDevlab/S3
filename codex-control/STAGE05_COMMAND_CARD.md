# Stage05 command card — Codex fast path

Use this file to avoid rereading the full control package during the paired Stage05 campaign.

This card never overrides `CURRENT.json` or `OVERRIDES.md`. If the revision changes, re-read those first.

## CURRENT STATE — REVISION 23 RECOVERY STOP

Context compaction mixed valid Stage05 work with an older PR #268/pre-IR/compaction route. Do not continue implementation until the recovery snapshot is returned.

Read:

```text
codex-control/RECOVERY_REV23_WORKTREE_RECONCILIATION.md
```

## Preserve these valid Stage05 results

```text
one-arg internal call -> structural good / Z3
ordered multi-arg internal call -> recovered to Z3
unresolved callee -> fail-closed
nested call with representable inner result -> pass
failing nested a + 1 fixture -> expression-lowering dependency that reproduces without call
```

Preserve:

- consumed-token legacy guard;
- comma/cursor repair #1;
- comma/cursor repair #2.

Do not label the `a + 1` limitation as a nested-call defect.

## Stop these drifted routes

Do not continue:

```text
arrays
foreign calls
old pre-IR/token-lane route
compaction 2x2 E0/E1
capacity planning
T4
benchmark
Stage06+
canonical mutation/restoration
implementation commits
```

## Recovery only

No new native build.

Capture:

```text
WORKTREE_HEAD
WORKTREE_BRANCH
GIT_STATUS_SHORT
CHANGED_FILES
CANONICAL_LOCAL_SHA256
CANONICAL_LOCAL_BYTES
CANONICAL_HEAD_SHA256
CANONICAL_HEAD_BYTES
CANONICAL_DIFF_PRESENT
CANONICAL_DIFF_PATCH_SAVED
STAGE05_CANDIDATE_SHA256
STAGE05_TRANSFORM_SHA256
STAGE05_TEMP_TELEMETRY_PRESENT
GUEST_FREE_BEFORE
GUEST_FREE_AFTER
OUT_OF_SPACE_ARTIFACT
```

Save canonical diff provenance before any future restore. Do not run `git reset --hard`, `git clean`, `git checkout --`, or `git restore` during revision 23.

Disk cleanup may remove only disposable `/tmp` files clearly created by the current diagnostic/cross-build attempts. Do not delete repository files, unknown untracked files, caches or toolchains.

Return the exact `PAIRING_RECOVERY_BEGIN ... PAIRING_RECOVERY_END` block from `RECOVERY_REV23_WORKTREE_RECONCILIATION.md`.

## Remote safety fact

Observed remote PR #268 HEAD remains:

```text
326d42f8a2623ced5a2151d6daaf2d67743faca8
```

The later route drift is therefore local/unpushed in the latest evidence.

## Authorization boundary during revision 23

New native build = NO
Implementation commit = NO
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
