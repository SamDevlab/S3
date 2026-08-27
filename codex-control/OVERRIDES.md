# Live overrides

CONTROL_REVISION: 27

## SNAPSHOT-ONLY HARD STOP

Revision 26 required read-only recovery. The supplied transcript nevertheless reports one more local qualifier edit and a plan to add two tests and run the focused compaction/lane suite.

The qualifier change is preserved as **unvalidated local work** because its contract is logically plausible:

```text
truncated/full-stream incomplete -> fail closed
textual assignment/value deltas != native observed deltas
block equality cannot be promoted under truncation
```

But this is still the old compaction route, not the active Stage05 lane.

The worktree is now reported as:

```text
12 files changed
```

## Do this now

Do not add the two planned tests.
Do not run the focused compaction/lane suite.
Do not edit the qualifier again.
Do not edit reports or sources.
Do not start any new compiler build or instrumentation.
Do not clean/delete anything from the worktree during the snapshot.

If an exact native PID was already alive before revision 27 is first read, that exact PID may only reach terminal state. Do not execute the produced output.

Capture only read-only recovery evidence:

1. worktree HEAD and branch;
2. exact `git status --short`;
3. exact changed and untracked file lists;
4. per-file diff stat/summary for all 12 reported changed files;
5. identify which changed files belong to Stage05 versus old compaction/report/qualifier drift;
6. canonical local SHA/bytes versus HEAD SHA/bytes;
7. save canonical diff provenance outside the repository if not already saved;
8. Stage05 candidate and transform SHA256 plus telemetry-marker presence;
9. identify the qualifier file just modified and its diff summary;
10. list existing temporary E0/E1/E0H/E1H artifacts without running or deleting them;
11. record guest free space;
12. return the recovery block and STOP.

## Preserve valid Stage05 evidence

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
```

No new tests.
No test execution.
No source/report/qualifier edit.
No new native build.
No matrix/fixture/histogram execution.
No cleanup/deletion during the snapshot.
No arrays, foreign calls, capacity work or Stage06+.
No canonical mutation/restore/revert.
No implementation commit.
No SELF_EMIT, Stage2, Stage3, T4 or benchmark.

## Authorization boundary

Existing already-running PID may finish = YES, exact existing PID only
Execute its output = NO
New native build = NO
New test file = NO
New test execution = NO
Source/report/qualifier edit = NO
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
