# Stage05 multi-argument evaluator diagnosis

Purpose: isolate the remaining multi-argument-only `Z 0` after parser/call-close recovery, without reopening arrays, capacity, callee resolution, or generic parser debugging.

This document does not authorize foreign calls, arrays, Stage06, canonical mutation, SELF_EMIT, Stage2, Stage3, or T4.

## Current evidence

Reported from the local PR #268 candidate:

```text
one-argument internal call:
  RC=0
  C emitted
  A ordered
  Z 3

unresolved callee:
  fail-closed preserved

multi-argument internal call:
  reaches C/A emission
  Z 0

capacity path:
  not failing

callee resolution:
  not the current blocker
```

Two comma/cursor defects have already been observed during this slice:

1. the comma branch advanced the cursor twice and skipped the next argument;
2. after the first repair, the comma was still revisited once, causing `has_arg=0` to be classified as an error.

Preserve the latest localized cursor repair. Do not reopen those earlier forms unless the new trace proves they remain the first setter.

## Current atomic probe

Finish only the evaluator-error telemetry already being executed.

Use the same instrumented binary for this A/B comparison:

```text
CONTROL: one-argument call known to remain structurally valid
REPRODUCER: ordered two-argument internal call
```

Capture only existing diagnostic markers at the call evaluator's actual error points. Do not add broader token/parser telemetry unless these markers are insufficient to locate the first setter.

Minimum useful summary:

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

Use the actual marker names if different. Missing fields should be reported as `NOT_RECORDED`, not guessed.

## Decision table

### A. Only two-arg trips argument compatibility/type/ordinal error

Owner:

```text
MULTI_ARG_ARGUMENT_COMPATIBILITY_OR_ORDINAL
```

Repair only the proven argument-index/type-state transition. Preserve one-arg behavior and source-order `A/O` edges.

### B. Two-arg arguments all pass, then result/return path trips

Owner:

```text
MULTI_ARG_POST_CALL_RESULT_OR_RETURN_STATE
```

Repair only the result/return state that differs after a multi-argument call. Do not touch comma parsing or callee resolution.

### C. One-arg also trips the same evaluator error

Owner:

```text
DEBUG_BINARY_OR_SHARED_EVALUATOR_REGRESSION
```

Stop. Do not use the multi-arg hypothesis until the one-arg positive control is restored on the same candidate/binary.

### D. No evaluator error marker trips, two-arg still ends Z0

Owner:

```text
POST_EVALUATOR_COMPLETENESS_OR_UNOBSERVED_SETTER
```

Regenerate cleanly and inspect only the first state/completeness condition after evaluator success. Do not return to parser instrumentation by default.

## Post-repair fast path

After one proven repair:

1. regenerate a clean candidate with all temporary telemetry removed;
2. run `s3 check` once;
3. record candidate SHA256;
4. build one Linux native binary;
5. record binary SHA256;
6. run exact zero-, one-, and ordered two-argument fixtures on the same binary;
7. stop on the first valid-call `Z 0` or malformed `C/A/O/R` data;
8. if the internal structures remain valid, run the stage-local strict Stage05 conformance gate on the one-argument fixture before arrays;
9. use verifier `errors[0]` only;
10. if strict PASS but masks remain `Z 3`, inspect only the Stage05/S3 completeness predicate rather than forcing bit 4.

## Locked work

Until this multi-argument evaluator blocker and the internal-call strict gate are stable:

- arrays remain locked;
- foreign calls remain locked;
- capacity changes remain locked;
- Stage06 remains locked;
- canonical mutation, SELF_EMIT, Stage2, Stage3 and T4 remain unauthorized.
