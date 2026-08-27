# Revision 24 — hard stop after already-running E1

This recovery instruction exists because revision 23 explicitly prohibited new native builds and the supplied transcript nevertheless reports that E0 was restarted and E1 was started on the older pre-IR/compaction 2x2 route.

This is a control-plane drift event, not Stage05 evidence.

## One allowed exception

At the moment revision 24 is first read:

- if the exact E1 native build reported in the transcript is still running, allow **that existing PID only** to reach terminal state;
- if E1 is already terminal, record its result only;
- if E1 is not running and has no terminal result, **do not restart it**.

No E0 restart. No E1 restart. No other native compiler build.

## Absolutely do not execute the 2x2 matrix

After E1 terminates (or is found already terminal/missing), do not execute any of the four E0/E1 × S0/S1 runs. Do not interpret E0/E1 as Stage05 proof.

The 2x2 route remains out of scope and unauthorized.

## Preserve valid Stage05 evidence

Keep these facts from the supplied transcript:

```text
one-arg internal call -> structural good / Z3
ordered multi-arg internal call -> recovered to Z3
unresolved callee -> fail-closed
nested call with representable inner result -> pass
nested fixture requiring a + 1 -> expression-lowering dependency reproduced without call
```

Keep these repairs:

1. comma double-advance repair;
2. comma revisit / has_arg=0 repair;
3. Stage05-consumed-token must not fall through to legacy redispatch.

Do not label the `a + 1` limitation as a nested-call defect.

## Disk evidence already reported

The supplied transcript reports:

```text
GUEST_FREE_BEFORE_CLEANUP=831 MB
GUEST_FREE_AFTER_CONTROLLED_TMP_CLEANUP=3.9 GB
E0_BUILD_RC=0
E1_BUILD=STARTED
```

Treat these as reported evidence only until repeated in the recovery checkpoint.

## Recovery snapshot after E1 terminal state

Without mutating repository content, capture:

```text
WORKTREE_HEAD
WORKTREE_BRANCH
GIT_STATUS_SHORT
CHANGED_FILES
UNTRACKED_FILES

CANONICAL_LOCAL_SHA256
CANONICAL_LOCAL_BYTES
CANONICAL_HEAD_SHA256
CANONICAL_HEAD_BYTES
CANONICAL_DIFF_PRESENT
CANONICAL_DIFF_PATCH_SAVED

STAGE05_CANDIDATE_SHA256
STAGE05_TRANSFORM_SHA256
STAGE05_TEMP_TELEMETRY_PRESENT

E0_BUILD_RC
E0_BINARY_OR_OUTPUT_SHA256 (if an existing final artifact is identifiable; otherwise NOT_RECORDED)
E1_STATUS
E1_BUILD_RC
E1_BINARY_OR_OUTPUT_SHA256 (if an existing final artifact is identifiable; otherwise NOT_RECORDED)

GUEST_FREE_AFTER_E1
```

Save any canonical diff patch outside the repository before any later restore/revert. Do not restore/revert canonical during revision 24.

## Forbidden

Do not run:

```text
git reset --hard
git clean
git checkout -- <path>
git restore <path>
```

Do not delete repository files, unknown untracked files, toolchains, or caches.
Do not start arrays, foreign calls, capacity work, Stage06, SELF_EMIT, Stage2, Stage3, T4, benchmark, or implementation commits.

## Required checkpoint

```text
PAIRING_RECOVERY_BEGIN
CONTROL_REVISION=24
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
E0_BUILD_RC=
E0_OUTPUT_SHA256=
E1_STATUS=
E1_BUILD_RC=
E1_OUTPUT_SHA256=
MATRIX_EXECUTIONS_AFTER_REV24=0
GUEST_FREE_AFTER_E1=
NEW_BUILD_STARTED_AFTER_REV24=NO
CANONICAL_RESTORED_OR_REVERTED=NO
IMPLEMENTATION_COMMIT_CREATED=NO
T4_EXECUTED=NO
BENCHMARK_EXECUTED=NO
FIRST_RECOVERY_BLOCKER=
PAIRING_RECOVERY_END
```

Stop after emitting this checkpoint. Do not resume Stage05 until a newer control revision clears the recovery stop.
