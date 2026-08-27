# Live overrides

CONTROL_REVISION: 26

## READ-ONLY RECOVERY STOP

Context compaction continued the old pre-IR/compaction campaign beyond revisions 23, 24 and 25. The latest supplied transcript now reports:

```text
E0 completed RC=0
E1 completed
2x2 matrix executed 4 times, all rc=2
E0(S0)=E0(S1)=1460/305/1213
E1(S0)=E1(S1)=1097/329/1213
common boundary=41502
five narrow discard fixtures executed
E0H completed
E1H started
post-compaction qualifier/report files edited locally
histogram interpretation: observable difference is opcode 5 only
first packed-token spill literal=1000000000000 at offset 41502
removed assignments=88492,88540
```

These facts are frozen as out-of-scope drift evidence. They do not promote Stage05 and do not authorize any further compaction qualification, histogram work or report editing.

Read first:

```text
codex-control/RECOVERY_REV26_READ_ONLY_SNAPSHOT.md
```

## Only allowed process exception

At first read of revision 26:

```text
IF an exact native PID from an already-started E1H/other command is still running:
    let only that exact existing PID reach terminal state
    DO NOT execute its output
ELSE:
    start nothing
```

After the existing PID terminates, all commands must be read-only state capture except saving the canonical diff patch and recovery transcript outside the repository.

## Preserve valid Stage05 evidence

```text
one-arg internal call -> structural good / Z3
ordered multi-arg internal call -> recovered to Z3
unresolved callee -> fail-closed
nested call with representable inner result -> pass
nested a + 1 fixture -> expression-lowering limitation reproduced without call
```

Preserve the two comma/cursor repairs and the Stage05-consumed-token legacy-dispatch guard.

## Current atomic task

Do not build, test or edit anything further.

Capture only:

1. worktree HEAD/branch/status/changed/untracked files;
2. local canonical SHA/bytes and HEAD canonical SHA/bytes;
3. canonical diff patch provenance saved outside the repository;
4. Stage05 candidate/transform SHA and telemetry presence;
5. report/qualifier files modified by the drift;
6. `/tmp` compaction/histogram artifacts present, without executing/deleting them;
7. E0/E1/E0H/E1H terminal state and hashes of existing outputs if available;
8. whether E0H/E1H were already executed and any already-existing histogram output;
9. guest free space;
10. exact revision-26 `PAIRING_RECOVERY_BEGIN ... PAIRING_RECOVERY_END` block;
11. STOP.

## Forbidden

```text
git reset --hard
git clean
git checkout -- <path>
git restore <path>
```

No source edit.
No report/qualifier edit.
No new native build.
No E0/E1/E0H/E1H restart.
No matrix/fixture/histogram execution.
No cleanup/deletion during this snapshot.
No arrays, foreign calls, capacity work or Stage06+.
No canonical mutation/restore/revert.
No implementation commit.
No SELF_EMIT, Stage2, Stage3, T4 or benchmark.

## Authorization boundary

Existing already-running PID may finish = YES, exact existing PID only
Execute its output = NO
New native build = NO
New test/execution = NO
Source/report edit = NO
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
