# Stage05 right-parenthesis close probe

Purpose: consume the latest paired evidence without broadening the Stage05 search space.

Stage05 remains active. This document does not authorize foreign calls, arrays, Stage06, canonical mutation, SELF_EMIT, Stage2, Stage3, or T4.

## Latest observed evidence

From the live Codex update supplied by the user:

- the clean candidate was regenerated after removing debug-only instrumentation;
- the clean native candidate completed compilation on the Linux guest;
- a grouping-vs-call same-binary probe was started, but the user-supplied excerpt does not include the grouping result, so it remains `NOT_REPORTED` here;
- the valid internal call still ends in `Z 0`;
- the call stream already emits structurally correct `C` and `A` records;
- prior diagnostics proved `helper(1)` becomes invalid during parsing before evaluation;
- static inspection confirmed `)` is token code `2` and the relevant call-close branch is the `current_code == 2` path;
- a new temporary diagnostic build is currently in flight and instruments only that correct close branch.

Do not convert the missing grouping result into PASS or FAIL.

## Current blocker

```text
VALID_INTERNAL_CALL_REJECTED_AT_OR_AROUND_RIGHT_PAREN_CALL_CLOSE
```

The semantic call records are not the first blocker for this fixture.

## Finish the current diagnostic build only

Do not start another native build while the current instrumented `current_code == 2` build is unresolved.

When it reaches terminal state, run only the same minimal `helper(1)` fixture and capture the temporary close-state fields around the call `)`:

```text
BEFORE_CLOSE_OP_COUNT=
BEFORE_CLOSE_PAREN_DEPTH=
BEFORE_CLOSE_ARITY=
BEFORE_CLOSE_ARGUMENT_FLAG=
BEFORE_CLOSE_PARSE_OK=

AFTER_CLOSE_OP_COUNT=
AFTER_CLOSE_PAREN_DEPTH=
AFTER_CLOSE_ARITY=
AFTER_CLOSE_ARGUMENT_FLAG=
AFTER_CLOSE_PARSE_OK=

EXIT_CODE=
Z_MASK=
```

Use the exact names/encodings actually emitted by the temporary probe if they differ; preserve the raw output.

## Classification

### A. `parse_ok` is already false before close

The right-paren closer is not the first setter. The next owning slice is the argument-stop / token-before-`)` path. Do not patch close bookkeeping yet.

### B. `parse_ok` changes from true to false inside close

The close branch owns the bug. Inspect exactly one of:

- invalid arity/argument-complete predicate;
- incorrect parenthesis/depth decrement;
- fallthrough into a generic `)` rejection after call close;
- call-frame restoration that writes `parse_ok=0`.

Patch only the exact condition proven by the raw values.

### C. `parse_ok` remains true after close but final `Z 0` persists

The parser-close blocker is cleared; the next blocker is later finalization/completeness. Regenerate the clean candidate and run strict Stage05 conformance before touching call parsing again.

## Grouping control

If the prior same-binary grouping result is available in Codex state, include it in the paired checkpoint. If it was not preserved, do **not** trigger another build just to recover it; both grouping and call can be rerun later on the clean post-fix binary.

## After reading the diagnostic

1. preserve raw diagnostic output;
2. regenerate the candidate cleanly so temporary markers disappear;
3. emit the paired checkpoint;
4. stop before another repair/build until the control plane is re-read.

## Success target after the eventual repair

For the minimal valid internal call:

```text
PARSE_OK_AFTER_RPN=-1
PARSE_OK_AFTER_EVAL=-1
PARSE_OK_FINAL=-1
CALL_OPCODE=14
C_RECORD=VALID_INTERNAL
A_ORDER=PASS
O_ORDER=PASS
R_RESULT=PASS_WHEN_APPLICABLE
STRICT_STAGE05_CONFORMANCE=PASS
Z_MASK=7
```

`Z 31` remains forbidden until S4/S5 close.
