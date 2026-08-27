# Live overrides

CONTROL_REVISION: 22

No emergency stop is active.

## Current direction

- Stage 04 remains accepted for transition as `PASS_REPORTED_PENDING_REMOTE_BACKFILL`.
- Stage 05 remains active under paired engineering mode.
- Automatic stage advance remains disabled.
- One-argument internal call remains the positive control (`RC=0`, `C`, ordered `A`, `Z3`).
- Unresolved callee fail-closed behavior remains reported intact.
- The evaluator is no longer the current owner: latest telemetry shows `parse_ok` is already zero before evaluator-error markers fire.
- The latest trace found a common-parenthesis/legacy-dispatch path reached by a token already consumed by Stage05.
- Preserve both previous comma/cursor repairs.
- Preserve the new localized consumed-token guard: a token explicitly consumed by Stage05 in the current cycle must not be processed/rejected again by the legacy dispatcher in that same cycle.
- Do not globally whitelist punctuation or parentheses; unconsumed/invalid tokens retain legacy fail-closed behavior.
- Read `codex-control/STAGE05_CONSUMED_TOKEN_LEGACY_GUARD.md` before any later permanent source edit.

## Current atomic task

A clean candidate containing the consumed-token guard is already reported in one native Linux build.

Finish that exact build. Do not start another build or source edit before it terminates.

Then reuse the same binary for:

```text
zero_arg_internal_call.s3
internal_one_arg_call.s3
ordered_two_arg_internal_call.s3
```

Record available evidence:

```text
EXIT_CODE=
Z_MASK=
CALL_OPCODE=
C_RECORD_PRESENT=
A_RECORD_COUNT=
A_VALUE_IDS_IN_SOURCE_ORDER=
O_RECORD_COUNT=
O_VALUE_IDS_IN_SOURCE_ORDER=
R_RECORD_COUNT=
PARSE_OK_FINAL=
```

Stop on the first valid-call `Z0`, parser regression or malformed `C/A/O/R` shape.

## Decision after build

```text
one-arg regresses
  -> stop; consumed-token guard may be too broad/shared state regressed

two-arg remains Z0
  -> preserve first remaining setter only; do not reopen capacity/evaluator by default

zero/one/two structurally valid
  -> run stage-local strict Stage05 conformance on the one-arg fixture

strict FAIL
  -> preserve verifier JSON
  -> consume errors[0] only

strict PASS + Z3
  -> inspect Stage05/S3 completeness predicate only
  -> do not force bit 4

strict PASS + Z7
  -> continue internal matrix on same binary: nested -> result reuse -> unresolved fail-closed
```

## Locked work

No arrays.
No foreign-call edits.
No capacity changes.
No generic parser/evaluator traces unless the new clean build directly requires one.
No Stage06 or later.

## Authorization boundary

Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
SELF_EMIT remains unauthorized.
Stage2 remains unauthorized.
Stage3 remains unauthorized.
T4 remains unauthorized.
Stage06 remains unauthorized.
