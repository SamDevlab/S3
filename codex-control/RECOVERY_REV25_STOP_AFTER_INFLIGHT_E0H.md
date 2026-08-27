# Revision 25 — hard stop after drifted histogram build

This is a recovery-only control. It does not authorize Stage05 promotion, arrays, foreign calls, compaction, T4, benchmarks, capacity work, or canonical mutation.

## Why this revision exists

The supplied Codex transcript shows revision-24 controls were exceeded:

- the full old 2x2 matrix was executed even though matrix execution was unauthorized;
- all four native runs reportedly returned rc=2 at the emitter boundary;
- reported summaries were `E0(S0)=E0(S1)=1460/305/1213` and `E1(S0)=E1(S1)=1097/329/1213`;
- both source variants reportedly stop at overflow offset 41502;
- five narrow discard fixtures reportedly showed one removed discard -> exactly one fewer event with calls/assignments/controls/returns unchanged and blocks unchanged;
- a new temporary histogram campaign was then started, with an E0H instrumented native build reported in flight.

These facts are preserved as **out-of-scope drift evidence only**. They do not alter the active Stage05 gate.

## Single process exception

At first read of revision 25:

```text
IF exact E0H PID is already running:
    allow only that exact PID to reach terminal state
ELSE IF E0H is already terminal:
    record terminal state only
ELSE:
    do not start or restart E0H
```

Do not run the produced E0H executable. Do not start E1H. Do not build another instrumented executable.

## Mandatory stop after E0H terminal state

No more compaction fixtures, histogram runs, 2x2 runs, Stage05 builds, or implementation edits.

Capture recovery state only:

1. worktree HEAD and branch;
2. `git status --short`;
3. changed files and untracked files;
4. local canonical SHA256/bytes;
5. HEAD canonical SHA256/bytes;
6. canonical diff presence;
7. save canonical diff patch outside the repository before any future restore/revert;
8. Stage05 candidate SHA256 and transform SHA256 if present;
9. Stage05 temporary telemetry presence;
10. list temporary compaction/histogram source, assembly, object and executable artifacts that exist;
11. E0/E1 terminal evidence already produced;
12. E0H terminal evidence if the exact pre-existing PID finishes;
13. guest free space;
14. confirm no E1H build and no histogram executable run;
15. confirm no new commit, canonical restore, T4 or benchmark.

Do not delete worktree files or untracked files during this snapshot. Do not run `git clean`, `git reset --hard`, `git checkout -- <path>`, or `git restore <path>`.

## Stage05 evidence to preserve

```text
one-arg internal call -> structural good / Z3
ordered multi-arg internal call -> recovered to Z3
unresolved callee -> fail-closed
nested call with representable inner result -> pass
nested a + 1 fixture -> expression-lowering limitation also reproduced without call
```

Retain the two comma/cursor repairs and the Stage05-consumed-token legacy-dispatch guard.

The next control revision, after reviewing the recovery checkpoint, decides how to restore the worktree and resume Stage05 strict conformance.

## Required checkpoint

```text
PAIRING_RECOVERY_BEGIN
CONTROL_REVISION=25
WORKTREE_HEAD=
WORKTREE_BRANCH=
REMOTE_PR268_HEAD=326d42f8a2623ced5a2151d6daaf2d67743faca8
GIT_STATUS_SHORT=
CHANGED_FILES=
UNTRACKED_FILES=
CANONICAL_LOCAL_SHA256=
CANONICAL_LOCAL_BYTES=
CANONICAL_HEAD_SHA256=
CANONICAL_HEAD_BYTES=
CANONICAL_DIFF_PRESENT=
CANONICAL_DIFF_PATCH_SAVED=
STAGE05_CANDIDATE_SHA256=
STAGE05_TRANSFORM_SHA256=
STAGE05_TEMP_TELEMETRY_PRESENT=
E0_BUILD_RC=0
E1_BUILD_RC=
MATRIX_RUN_COUNT=4
MATRIX_E0_S0=
MATRIX_E0_S1=
MATRIX_E1_S0=
MATRIX_E1_S1=
MATRIX_COMMON_OVERFLOW_OFFSET=
HISTOGRAM_TEMP_FILES=
E0H_STATUS=
E0H_BUILD_RC=
E0H_OUTPUT_SHA256=
E0H_EXECUTED=NO
E1H_STARTED=NO
NEW_BUILD_STARTED_AFTER_REV25=NO
GUEST_FREE=
CANONICAL_RESTORED_OR_REVERTED=NO
IMPLEMENTATION_COMMIT_CREATED=NO
T4_EXECUTED=NO
BENCHMARK_EXECUTED=NO
FIRST_RECOVERY_BLOCKER=
PAIRING_RECOVERY_END
```
