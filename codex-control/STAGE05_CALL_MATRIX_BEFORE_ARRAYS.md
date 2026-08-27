# Stage05 call matrix before arrays

Purpose: consume the post-parser recovery evidence and prevent premature expansion into arrays before internal call semantics are proven.

## Current evidence

The Stage05 parser fixes now allow a simple internal call to execute natively with `RC=0`, emit `C` plus ordered `A`, and finish at `Z 3` rather than `Z 0`.

This is meaningful progress, but `Z 3` does not close S3. It means the candidate is no longer failing closed at the parser boundary while the Stage05/S3 claim is still absent.

A separate multi-argument bug was then found: the comma branch advanced the source/token cursor twice, skipping the next argument. That repair is within the internal-call slice and should be preserved if the in-flight build validates it.

## Current atomic sequence

Finish the already-running native build containing the comma-cursor repair. Do not start a second build in parallel.

Then reuse the same unchanged binary for:

1. `zero_arg_internal_call.s3`
2. `internal_one_arg_call.s3`
3. `ordered_two_arg_internal_call.s3`

For each record:

```text
EXIT_CODE=
Z_MASK=
CALL_OPCODE=
C_RECORD_PRESENT=
C_CALLEE_KIND=
A_RECORD_COUNT=
A_VALUE_IDS_IN_SOURCE_ORDER=
O_RECORD_COUNT=
O_VALUE_IDS_IN_SOURCE_ORDER=
R_RECORD_COUNT=
PARSE_OK_FINAL=
```

If any valid internal call regresses to `Z 0`, stop at that fixture and preserve the first failure.

## Strict conformance gate before arrays

If zero/one/two-argument calls all parse and structurally emit call data, run the current stage-local strict conformance gate on the smallest valid one-argument call **before editing arrays**.

Do not assume `Z 3` itself identifies the next bug. First determine whether the stage-local verifier says the `I/O/R/C/A` semantics are conformant.

Decision:

```text
strict conformance FAIL
  -> use errors[0] only
  -> repair one semantic owner

strict conformance PASS, final Z remains 3
  -> inspect only the candidate's Stage05/S3 completeness-mask predicate
  -> determine which required Stage05 condition has not yet been proven/set
  -> do not synthesize bit 4 merely because C/A records exist

strict conformance PASS, final Z becomes 7
  -> internal one-call S3 proof is ready
  -> continue internal-call regression matrix on same binary
```

## Internal call order after first strict PASS

```text
zero arg
one arg
ordered two arg
nested internal call
call result reuse
unresolved callee fail-closed
```

Only after these internal call semantics are stable should the control plane unlock foreign calls, then arrays/indexing.

## Why arrays are frozen for now

Stage05 exit requires both S3 call dataflow and the required array/index subset. Starting arrays while internal call ordering/result identity or the S3 completeness predicate is still unresolved would mix independent blocker classes and increase rebuild/debug cycles.

## Authorization boundary

Do not edit arrays yet.
Do not edit foreign-call lowering yet.
Do not change capacity yet.
Do not advance to Stage06.
Canonical Stage1 mutation remains unauthorized.
SELF_EMIT remains unauthorized.
Stage2/Stage3/T4 remain unauthorized.
