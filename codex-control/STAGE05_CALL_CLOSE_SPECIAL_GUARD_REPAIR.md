# Stage05 call-close special guard repair

Purpose: freeze the second proven Stage05 parser root cause after the special-open guard.

This document does not authorize foreign calls, arrays, Stage06, canonical mutation, SELF_EMIT, Stage2, Stage3 or T4.

## Proven second root cause

Latest token trace on the already-guarded candidate establishes:

1. `parse_ok` remains valid (`-1`) through callee detection and argument processing;
2. the matching `)` is reached with a valid call frame and valid computed arity;
3. the Stage05 call-close logic recognizes the frame;
4. the legacy punctuation/operand dispatcher still sees the same `)` token as unrecognized punctuation and writes `parse_ok = 0` in the same token cycle;
5. this behavior is shared by zero-argument and one-argument internal calls, so it is not an argument-count-specific bug.

Current blocker:

```text
VALID_CALL_CLOSE_TOKEN_FALLS_THROUGH_LEGACY_PUNCTUATION_REJECTION
```

## Single repair owner

Mark only a `RIGHT_PAREN` that is proven to close an active Stage05 call frame as a Stage05-special close token for the duration of that token cycle.

Semantic intent:

```text
if current token is ')' and it closes a valid active Stage05 call frame:
    keep all Stage05 call-close validation active
    compute/validate arity normally
    finish the Stage05 call frame normally
    do not let the same ')' fall through to legacy unknown-punctuation rejection
    preserve parse_ok unless Stage05's own validation fails
else:
    preserve all legacy punctuation behavior exactly
```

Do not globally whitelist `)`. Do not bypass unmatched-paren/grouping errors. Do not change call arity rules. Do not revisit `stage05_open_kind > 0` truth semantics.

## Current in-flight action

A native build containing this localized call-close special guard is already reported in flight. Finish that exact build. Do not start another build or source repair until it reaches terminal state.

## Post-build proof

Using the same resulting binary:

1. run exact pinned `zero_arg_internal_call.s3`;
2. run exact pinned `internal_one_arg_call.s3`;
3. record exit code, final `Z`, and presence/shape of call records;
4. if either valid call still reaches `Z 0`, preserve the first raw parse/completeness failure and stop broadening;
5. if parser remains valid and both reach Stage05 mask `Z 7`, run strict Stage05 conformance immediately on `internal_one_arg_call.s3`;
6. preserve verifier JSON and consume only `errors[0]` for the next repair owner;
7. only after strict conformance passes may the same unchanged binary proceed through later internal-call regressions.

## Expected first-slice target

```text
ZERO_ARG_INTERNAL_CALL=VALID
ONE_ARG_INTERNAL_CALL=VALID
CALL_OPCODE=14
C_INTERNAL=VALID
A_ORDER=PASS
O_ORDER=PASS
R_RESULT=PASS_WHEN_APPLICABLE
STRICT_STAGE05_CONFORMANCE=PASS
Z_MASK=7
```

`Z 31` is not a Stage05 target.
