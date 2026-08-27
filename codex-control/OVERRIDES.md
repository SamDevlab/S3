# Live overrides

CONTROL_REVISION: 21

No emergency stop is active.

## Current direction

- Stage 04 remains accepted for transition as `PASS_REPORTED_PENDING_REMOTE_BACKFILL`.
- Stage 05 remains active under paired engineering mode.
- Automatic stage advance remains disabled.
- The simple one-argument internal call remains a positive control: reported `RC=0`, `C` emitted, ordered `A` emitted, final `Z 3`.
- Unresolved callee fail-closed behavior remains reported intact.
- Multi-argument calls now reach `C/A` emission but still finish `Z 0`.
- Capacity and callee resolution are not the reported current blocker.
- Two comma/cursor defects were found in sequence and their latest localized repair must be preserved:
  1. double cursor advance skipped the next argument;
  2. residual comma revisit made `has_arg=0` look like an error.
- Do not reopen parser/call-close work unless the current evaluator telemetry directly contradicts the recovered one-argument control.
- Read `codex-control/STAGE05_MULTIARG_EVALUATOR_DIAGNOSIS.md` before the next permanent source edit.

## Current atomic task

Finish only the evaluator-error telemetry already in progress.

Use the same instrumented binary for:

```text
CONTROL: known-good one-argument internal call
REPRODUCER: ordered two-argument internal call
```

Capture the first existing evaluator error marker that differs between the two runs.

Useful summary:

```text
ONE_ARG_EXIT=
ONE_ARG_Z=
ONE_ARG_EVAL_ERROR_MARKER=

TWO_ARG_EXIT=
TWO_ARG_Z=
TWO_ARG_EVAL_ERROR_MARKER=
TWO_ARG_ERROR_ARGUMENT_ORDINAL=
TWO_ARG_EXPECTED_TYPE=
TWO_ARG_ACTUAL_TYPE=
TWO_ARG_RESULT_OR_RETURN_ERROR=
```

Use `NOT_RECORDED` for unavailable fields. Do not add broader parser/token instrumentation unless these existing evaluator markers cannot identify the first owner.

## Decision

```text
one-arg clean; two-arg trips argument compatibility/type/ordinal
  -> MULTI_ARG_ARGUMENT_COMPATIBILITY_OR_ORDINAL
  -> fix only that argument-state transition

one-arg clean; two-arg arguments pass; result/return trips
  -> MULTI_ARG_POST_CALL_RESULT_OR_RETURN_STATE
  -> fix only the post-call result/return state

one-arg trips the same evaluator error
  -> DEBUG_BINARY_OR_SHARED_EVALUATOR_REGRESSION
  -> stop the multiarg hypothesis until the positive control is restored

no evaluator marker trips; two-arg still Z0
  -> POST_EVALUATOR_COMPLETENESS_OR_UNOBSERVED_SETTER
  -> leave parser alone and inspect the first post-evaluator state/completeness condition
```

## After one proven repair

1. regenerate cleanly with all temporary telemetry removed;
2. `s3 check` once;
3. record candidate SHA256;
4. build one Linux native binary;
5. record binary SHA256;
6. run exact pinned zero-, one-, and ordered two-argument fixtures on that same binary;
7. stop on the first valid-call `Z 0` or malformed `C/A/O/R` shape;
8. if those calls remain structurally valid, run the current stage-local strict Stage05 conformance gate on the one-argument fixture;
9. strict FAIL -> consume `errors[0]` only;
10. strict PASS + `Z 3` -> inspect only the Stage05/S3 completeness predicate; do not force bit 4;
11. strict PASS + `Z 7` -> continue internal call regressions on the same binary.

## Locked work

Do not spend time on:

- arrays;
- foreign calls;
- capacity changes;
- generic parser/call-close traces;
- SSH/Linux/Python/cc requalification;
- Stage04 expression matrix;
- Stage06 or later.

## Authorization boundary

Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
SELF_EMIT remains unauthorized.
Stage2 remains unauthorized.
Stage3 remains unauthorized.
T4 remains unauthorized.
Stage06 remains unauthorized.
