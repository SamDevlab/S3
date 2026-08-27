# Live overrides

CONTROL_REVISION: 25

## HARD STOP — HISTOGRAM DRIFT MUST END

Revision 24 authorized only an already-running E1 process to finish, then required zero matrix executions and a recovery snapshot. The supplied transcript nevertheless reports:

```text
E0_BUILD_RC=0
E1_BUILD=COMPLETED
2x2 native matrix runs=4
all matrix rc=2
E0(S0)=E0(S1)=1460/305/1213
E1(S0)=E1(S1)=1097/329/1213
common overflow offset=41502
five narrow discard fixtures executed
new temporary histogram campaign started
E0H build reported in flight
```

These results are preserved as out-of-scope drift evidence only. They do not promote Stage05 and do not authorize further compaction work.

Read first:

```text
codex-control/RECOVERY_REV25_STOP_AFTER_INFLIGHT_E0H.md
```

## Single allowed process exception

At first read of revision 25:

```text
IF exact E0H PID is already running:
    let only that exact PID reach terminal state
ELSE IF E0H is already terminal:
    record terminal result only
ELSE:
    DO NOT start/restart E0H
```

After E0H terminal state:

```text
DO NOT execute E0H
DO NOT start E1H
DO NOT build any other instrumented executable
DO NOT run any more 2x2/fixture/compaction tests
```

No new native compiler build of any kind.

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

1. Finish only the exact already-running E0H PID if it exists.
2. Do not execute its output.
3. Do not start E1H.
4. Capture worktree HEAD/branch/status/changed/untracked files.
5. Capture local canonical SHA/bytes and HEAD canonical SHA/bytes.
6. Save canonical diff patch provenance outside the repository.
7. Capture Stage05 candidate/transform SHA and telemetry presence.
8. List temporary compaction/histogram artifacts currently present.
9. Record E0/E1/matrix evidence already produced and E0H terminal evidence if applicable.
10. Record guest free space.
11. Return the exact revision-25 `PAIRING_RECOVERY_BEGIN ... PAIRING_RECOVERY_END` checkpoint.
12. STOP.

## Forbidden

```text
git reset --hard
git clean
git checkout -- <path>
git restore <path>
```

No worktree deletion or cleanup during this snapshot. No arrays, foreign calls, capacity work, Stage06, canonical mutation/restore/revert, implementation commits, SELF_EMIT, Stage2, Stage3, T4 or benchmark.

## Authorization boundary

New native build = NO
Already-running E0H may finish = YES, exact existing PID only
Execute E0H = NO
Start E1H = NO
2x2/fixture/histogram executions = NO
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
