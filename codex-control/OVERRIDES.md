# Live overrides

CONTROL_REVISION: 13

No emergency stop is active.

## Current direction

- Stage 04 remains accepted for transition as `PASS_REPORTED_PENDING_REMOTE_BACKFILL`; preserve/push the local Stage04 checkpoint on the next implementation commit without fabricating remote evidence.
- Stage 05 remains active under paired engineering mode.
- Automatic stage advance remains disabled.
- Finish the already in-flight `current_code == 2` right-parenthesis diagnostic build before applying any new repair.
- Read `codex-control/STAGE05_RIGHT_PAREN_CLOSE_PROBE.md` and `codex-control/STAGE05_POSTFIX_ORACLE.md` before the next edit.

## Latest paired evidence

```text
valid internal call still ends Z 0
C record structurally emitted
A record structurally emitted
prior failure phase = parser, before evaluation
RIGHT_PAREN token code = 2
owning close branch under diagnosis = current_code == 2
```

The grouping-control result from the earlier A/B probe was not included in the supplied excerpt, so it remains `NOT_REPORTED`. Do not infer it.

The first blocker remains:

```text
VALID_INTERNAL_CALL_REJECTED_AT_OR_AROUND_RIGHT_PAREN_CALL_CLOSE
```

## Authoritative postfix oracle

Repository test coverage confirms these are valid parser forms:

```text
f()
f(a, b)
(a).b
f().value
pkg.function()
factory()[0]
functions[0]()
consume(pkg.make().value)
a[0].b(c)[1]
(factory())[0]
```

The explicit negative boundary is:

```text
f(1   -> expected ')' after arguments
f(a,) -> expected argument after ','
```

Therefore a complete `helper(1)` must not fail merely because `RIGHT_PAREN` is encountered. Call parentheses are postfix-call delimiters and the matching close is consumed exactly once by the call closer.

Do **not** patch from this oracle alone. Use the current close diagnostic to prove where `parse_ok` first changes.

## Required close-state observation

When the current build terminates, run only the same minimal `helper(1)` fixture and preserve raw output. Capture:

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

Use the actual debug marker names if different.

## Classification and one repair only

If `parse_ok` is already false before close:

```text
NEXT_OWNER=ARGUMENT_STOP_OR_TOKEN_BEFORE_RIGHT_PAREN
```

If `parse_ok` flips from true to false inside close:

```text
NEXT_OWNER=RIGHT_PAREN_CALL_CLOSE
```

Use the raw state to choose exactly one proven failing condition: argument-complete/arity validation, parenthesis/depth decrement, fallthrough into a generic `)` rejection, or call-frame restoration.

If `parse_ok` remains true after close but final `Z 0` persists:

```text
NEXT_OWNER=POST_PARSE_FINALIZATION_OR_COMPLETENESS
```

Regenerate cleanly and run strict Stage05 conformance before touching the call parser again.

## After the diagnostic

1. preserve raw stdout/stderr/exit and exact candidate/binary hashes if available;
2. regenerate the clean candidate so temporary diagnostics disappear;
3. emit a paired checkpoint;
4. re-read control before another repair/build.

Do not trigger another build solely to recover the missing grouping result.

## First internal-call success boundary

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

## Do not broaden

Until the first valid internal call is conformant:

- no zero-arg expansion;
- no multi-arg or nested expansion;
- no foreign calls;
- no arrays;
- no capacity changes;
- no Stage06.

## Authorization boundary

Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
SELF_EMIT remains unauthorized.
Stage2 remains unauthorized.
Stage3 remains unauthorized.
T4 remains unauthorized.
Stage06 remains unauthorized.
