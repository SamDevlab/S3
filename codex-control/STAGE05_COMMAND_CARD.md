# Stage05 command card — Codex fast path

Use this file to avoid rereading the full control package during the current paired Stage05 campaign.

This card never overrides `CURRENT.json` or `OVERRIDES.md`. If the revision changes, re-read those first.

## Current atomic task — revision 21

Current positive control:

```text
one-argument internal call
RC=0
C emitted
A emitted in source order
Z=3
```

Unresolved callee remains fail-closed.

Current reproducer:

```text
ordered multi-argument internal call
C/A emission reached
Z=0
```

Capacity and callee resolution are not the current reported blocker.

Two comma/cursor bugs were already found and repaired locally in sequence:

```text
1. comma branch advanced cursor twice -> next argument skipped
2. comma was revisited once -> has_arg=0 classified as error
```

Preserve the latest localized cursor repair.

Read:

```text
codex-control/STAGE05_MULTIARG_EVALUATOR_DIAGNOSIS.md
```

## Finish the evaluator telemetry already running

Use the same instrumented binary for A/B:

```text
A = one-argument positive control
B = ordered two-argument reproducer
```

Do not add broad parser traces.

Record the first evaluator error marker that differs:

```text
ONE_ARG_EXIT
ONE_ARG_Z
ONE_ARG_EVAL_ERROR_MARKER

TWO_ARG_EXIT
TWO_ARG_Z
TWO_ARG_EVAL_ERROR_MARKER
TWO_ARG_ERROR_ARGUMENT_ORDINAL
TWO_ARG_EXPECTED_TYPE
TWO_ARG_ACTUAL_TYPE
TWO_ARG_RESULT_OR_RETURN_ERROR
```

Missing = `NOT_RECORDED`.

## Immediate decision

```text
only B trips argument compatibility/type/ordinal
  -> fix MULTI_ARG_ARGUMENT_COMPATIBILITY_OR_ORDINAL only

B arguments pass; result/return trips
  -> fix MULTI_ARG_POST_CALL_RESULT_OR_RETURN_STATE only

A trips the same evaluator marker
  -> stop: DEBUG_BINARY_OR_SHARED_EVALUATOR_REGRESSION

no evaluator marker; B still Z0
  -> POST_EVALUATOR_COMPLETENESS_OR_UNOBSERVED_SETTER
  -> do not return to generic parser work
```

## After one proven repair

```text
clean regenerate
-> s3 check once
-> candidate SHA
-> one Linux build
-> binary SHA
-> zero arg
-> one arg
-> ordered two arg
```

All three use the same binary. Stop at first unexpected result.

Then, before arrays or foreign calls:

```text
stage-local strict Stage05 conformance on one-arg fixture
```

Decision:

```text
strict FAIL
  -> errors[0] only

strict PASS + Z3
  -> inspect Stage05/S3 completeness predicate only
  -> do not force bit 4

strict PASS + Z7
  -> continue internal call matrix:
     nested -> result reuse -> unresolved fail-closed
```

## Locked

No arrays yet.
No foreign-call edits yet.
No capacity changes.
No Stage06.
No canonical mutation.
No SELF_EMIT.
No Stage2/Stage3/T4.
