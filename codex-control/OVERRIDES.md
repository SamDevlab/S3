# Live overrides

CONTROL_REVISION: 23

## TEMPORARY EMERGENCY RECONCILIATION STOP

A context-compaction drift mixed the valid paired Stage05 call campaign with an older PR #268/pre-IR/compaction route. Until the revision-23 recovery checkpoint is returned, the only authorized work is **state capture plus narrowly-scoped temporary-disk cleanup**.

Read first:

```text
codex-control/RECOVERY_REV23_WORKTREE_RECONCILIATION.md
```

## Valid Stage05 progress that must be preserved

Latest supplied evidence before the route drift reports:

```text
one-arg internal call -> structural good / Z3
ordered multi-arg internal call -> recovered to Z3
unresolved callee -> fail-closed
nested call with representable inner result -> pass
nested fixture using a + 1 -> fails because arithmetic expression lowering is limited
same a + 1 limitation reproduces without a call
```

Therefore do **not** relabel the arithmetic dependency as a nested-call bug, and do not discard the consumed-token guard or the two comma/cursor repairs.

## Out-of-scope drift that must stop now

Do not continue:

- array lowering/inspection;
- foreign-call lowering;
- old pre-IR/token-lane/compaction route;
- E0/E1 2x2 cross-build experiments;
- T4;
- benchmarks;
- capacity planning;
- Stage06 or later;
- canonical promotion/restoration/mutation;
- implementation commits.

The remote PR #268 HEAD observed by ChatGPT is still:

```text
326d42f8a2623ced5a2151d6daaf2d67743faca8
```

so the later drift is local/unpushed and must be reconciled before any promotion.

## Current atomic task

Do **not** start a new compiler build.

1. If the previously running build already ended, record only its terminal state.
2. Capture current worktree HEAD/branch/status/diff summary.
3. Capture local canonical SHA256/bytes and HEAD canonical SHA256/bytes.
4. Save the canonical diff as a patch outside the repository before any future restore/revert.
5. Capture Stage05 candidate and transform SHA256 if present.
6. Confirm whether temporary Stage05 telemetry remains in the candidate/transform.
7. Record guest free-space state.
8. Remove only disposable `/tmp` artifacts clearly created by the current Stage05/2x2 diagnostic attempts; do not delete repository files, toolchains, caches, or unknown untracked worktree files.
9. Record free-space state again.
10. Return the exact `PAIRING_RECOVERY_BEGIN ... PAIRING_RECOVERY_END` block from the revision-23 recovery file.

## Destructive commands forbidden during recovery

Do not run:

```text
git reset --hard
git clean
git checkout -- <canonical>
git restore <canonical>
```

Do not delete untracked worktree files before listing them. Do not revert the canonical file yet; its provenance must be captured first.

## Authorization boundary

New native build = NO
Implementation commit = NO
Canonical mutation = NO
Canonical restore/revert = NO until next control revision
SELF_EMIT = NO
Stage2 = NO
Stage3 = NO
T4 = NO
Benchmark = NO
Stage06 = NO
Arrays = NO
Foreign calls = NO

The next control revision will resume Stage05 from the preserved call evidence after this reconciliation is reviewed.
