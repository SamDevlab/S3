# Revision 26 — read-only recovery snapshot

This control revision hard-stops all implementation and experiment drift after context compaction continued beyond revisions 23, 24 and 25.

## Preserved evidence only

The following supplied facts are retained as **out-of-scope drift evidence**, not Stage05 promotion evidence:

```text
E0 build completed RC=0
E1 build completed
2x2 matrix executed 4 native runs, all rc=2
E0(S0)=E0(S1)=1460/305/1213
E1(S0)=E1(S1)=1097/329/1213
common packed-token/overflow boundary offset=41502
five narrow discard fixtures reported one fewer event per removed discard with calls/assignments/controls/returns/blocks otherwise unchanged
E0H histogram build completed successfully
E1H histogram build was started
post-compaction report/qualifier edits were performed locally
histogram interpretation reported: compaction changes only opcode 5 in the observable prefix; other opcode lanes are identical
first packed-token spill reported at literal 1000000000000 at offset 41502
removed assignments reported at offsets 88492 and 88540, after the spill boundary
```

Interpretation may be preserved as a note only:

```text
The native prefix truncates before the textual discard removals, so identical pre-overflow assignment/value observations do not disprove the discard-only transformation. Full-source promotion remains blocked by packed-token coverage.
```

Do not extend, qualify, publish, promote, calibrate, or further test this old compaction route in revision 26.

## Valid Stage05 evidence to preserve

```text
one-argument internal call -> structural good / Z3
ordered multi-argument internal call -> recovered to Z3
unresolved callee -> fail-closed
nested call with representable inner result -> pass
nested a + 1 fixture -> expression-lowering limitation reproduced without a call
```

Retain:

- comma double-advance repair;
- comma revisit / has_arg=0 repair;
- Stage05-consumed-token legacy-dispatch guard.

Do not classify the `a + 1` dependency as a nested-call defect.

## Hard stop rule

At first read of revision 26:

```text
IF any native compiler PID from E1H or another already-started command is still running:
    allow only that exact existing PID to reach terminal state
    do not run its output
ELSE:
    start nothing
```

After existing PID terminal state, all further commands must be read-only state capture except writing the canonical diff patch and recovery transcript outside the repository.

## Authorized operations only

1. `git status --short` / branch / HEAD reads.
2. List changed and untracked files; do not delete them.
3. Hash and byte-count local canonical, HEAD canonical, Stage05 candidate and Stage05 transform.
4. Save the canonical diff patch outside the repository, if not already saved.
5. List local report/qualifier files modified by the drift.
6. List `/tmp` compaction/histogram artifacts; do not execute or delete them in revision 26.
7. Record E0/E1/E0H/E1H terminal state and hashes of already-existing executables when available.
8. Record whether E0H/E1H were executed and any already-existing histogram output; do not execute them now.
9. Record guest disk free space.
10. Return the exact recovery block below and stop.

## Forbidden

No source/report/qualifier edit.
No new native build.
No E0/E1/E0H/E1H restart.
No matrix/fixture/histogram execution.
No arrays or foreign calls.
No capacity work.
No Stage06+.
No canonical mutation, restore or revert.
No implementation commit.
No `git reset --hard`, `git clean`, `git checkout -- <path>`, or `git restore <path>`.
No SELF_EMIT, Stage2, Stage3, T4 or benchmark.
No merge.

## Required checkpoint

```text
PAIRING_RECOVERY_BEGIN
CONTROL_REVISION=26
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

DRIFT_MODIFIED_REPORT_FILES=
DRIFT_MODIFIED_QUALIFIER_FILES=

E0_BUILD_RC=0
E1_BUILD_RC=
E0_OUTPUT_SHA256=
E1_OUTPUT_SHA256=

MATRIX_RUN_COUNT=4
MATRIX_E0_S0=1460/305/1213
MATRIX_E0_S1=1460/305/1213
MATRIX_E1_S0=1097/329/1213
MATRIX_E1_S1=1097/329/1213
MATRIX_COMMON_OVERFLOW_OFFSET=41502

E0H_STATUS=
E0H_BUILD_RC=
E0H_OUTPUT_SHA256=
E0H_EXECUTED=

E1H_STATUS=
E1H_BUILD_RC=
E1H_OUTPUT_SHA256=
E1H_EXECUTED=

HISTOGRAM_ALREADY_OBSERVED=
HISTOGRAM_OPCODE5_ONLY_DIFFERENCE_REPORTED=YES
FIRST_PACKED_TOKEN_SPILL_LITERAL=1000000000000
FIRST_PACKED_TOKEN_SPILL_OFFSET=41502
REMOVED_ASSIGNMENT_OFFSETS=88492,88540

TMP_COMPACTION_HISTOGRAM_ARTIFACTS=
GUEST_FREE=

NEW_BUILD_STARTED_AFTER_REV26=NO
NEW_TEST_EXECUTED_AFTER_REV26=NO
SOURCE_OR_REPORT_EDIT_AFTER_REV26=NO
CANONICAL_RESTORED_OR_REVERTED=NO
IMPLEMENTATION_COMMIT_CREATED=NO
T4_EXECUTED=NO
BENCHMARK_EXECUTED=NO

FIRST_RECOVERY_BLOCKER=
PAIRING_RECOVERY_END
```

After returning this block, stop and wait for a newer control revision. The next revision will separate/preserve Stage05 work from the older compaction drift before resuming strict Stage05 conformance.
