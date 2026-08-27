# Live overrides

CONTROL_REVISION: 24

## HARD RECOVERY STOP AFTER REVISION-23 DRIFT

Revision 23 prohibited new native builds, E0/E1 2x2 work, arrays, T4, benchmark and canonical mutation. The supplied transcript nevertheless reports:

```text
controlled /tmp cleanup: 831 MB -> 3.9 GB free
E0 restarted after the stop
E0_BUILD_RC=0
E1 started after the stop
```

This is control-plane drift, not Stage05 promotion evidence.

Read first:

```text
codex-control/RECOVERY_REV24_STOP_AFTER_INFLIGHT_E1.md
```

## Only allowed process exception

At first read of revision 24:

```text
IF exact E1 PID is already running:
    let that existing PID reach terminal state
ELSE IF E1 is already terminal:
    record terminal result only
ELSE:
    DO NOT start/restart E1
```

No E0 restart. No E1 restart. No other native compiler build.

After E1 terminal state: **do not execute any of the four 2x2 matrix runs**.

## Preserve valid Stage05 evidence

```text
one-arg internal call -> structural good / Z3
ordered multi-arg internal call -> recovered to Z3
unresolved callee -> fail-closed
nested call with representable inner result -> pass
nested a + 1 fixture -> expression-lowering dependency reproduced without a call
```

Preserve the two comma/cursor repairs and the Stage05-consumed-token legacy-dispatch guard.

Do not relabel the `a + 1` limitation as a nested-call defect.

## Current atomic task

1. Finish only the exact already-running E1 PID if it exists.
2. Execute zero matrix runs.
3. Capture worktree HEAD/branch/status/changed/untracked files.
4. Capture local canonical SHA/bytes and HEAD canonical SHA/bytes.
5. Save canonical diff patch provenance outside the repository.
6. Capture Stage05 candidate/transform SHA and telemetry presence.
7. Record E0/E1 terminal evidence and output hashes if existing artifacts are identifiable.
8. Record guest free space after E1.
9. Return the exact revision-24 `PAIRING_RECOVERY_BEGIN ... END` checkpoint.
10. Stop. Wait for a newer control revision before resuming Stage05.

## Forbidden

```text
git reset --hard
git clean
git checkout -- <path>
git restore <path>
```

Do not delete repository files, unknown untracked files, toolchains or caches.
Do not start arrays, foreign calls, capacity work, Stage06, canonical restore/mutation, implementation commits, SELF_EMIT, Stage2, Stage3, T4 or benchmark.

## Authorization boundary

New native build = NO
Already-running E1 may finish = YES, exact existing PID only
2x2 matrix executions = NO
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
