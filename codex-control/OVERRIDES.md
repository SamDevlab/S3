# Live overrides

CONTROL_REVISION: 12

No emergency stop is active.

## Current direction

- Stage 04 remains accepted for transition as `PASS_REPORTED_PENDING_REMOTE_BACKFILL`; preserve/push the local Stage04 checkpoint on the next implementation commit without fabricating remote evidence.
- Stage 05 remains active under paired engineering mode.
- Automatic stage advance remains disabled.
- Read `codex-control/STAGE05_RIGHT_PAREN_CLOSE_PROBE.md` before the next Stage05 action.

## Latest paired evidence

The latest user-supplied Codex state establishes:

```text
valid internal call still ends Z 0
C record structurally emitted
A record structurally emitted
prior failure phase = parser, before evaluation
RIGHT_PAREN token code = 2
owning close branch = current_code == 2
```

The grouping-control result from the prior same-binary A/B probe was not included in the supplied excerpt, so it remains `NOT_REPORTED`. Do not infer PASS or FAIL.

The first blocker is now:

```text
VALID_INTERNAL_CALL_REJECTED_AT_OR_AROUND_RIGHT_PAREN_CALL_CLOSE
```

A narrowly instrumented native build of the correct `current_code == 2` close branch is already reported in flight. Finish that exact build. Do not start another build or add more instrumentation while it is unresolved.

## Required close-state observation

Run only the same minimal `helper(1)` fixture and preserve raw output. Capture the close-state fields already instrumented around the matching `)`:

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

Use the actual marker names/encodings from the debug artifact if different.

## Classification and one repair only

If `parse_ok` is already false before the close branch:

```text
NEXT_OWNER=ARGUMENT_STOP_OR_TOKEN_BEFORE_RIGHT_PAREN
```

Do not modify close bookkeeping yet.

If `parse_ok` changes from true to false inside the close branch:

```text
NEXT_OWNER=RIGHT_PAREN_CALL_CLOSE
```

Use the raw state to identify exactly one proven failing condition among arity/argument completion, depth decrement, fallthrough into generic `)` rejection, or call-frame restoration. Patch only that condition.

If `parse_ok` remains true after close but final `Z 0` persists:

```text
NEXT_OWNER=POST_PARSE_FINALIZATION_OR_COMPLETENESS
```

Regenerate the clean candidate and run strict Stage05 conformance before touching the call parser again.

## After the diagnostic

1. preserve raw stdout/stderr/exit and candidate/binary identities if available;
2. regenerate the clean candidate so temporary diagnostics disappear;
3. emit a `PAIRING_CHECKPOINT`;
4. re-read control before another repair/build.

Do not trigger another build solely to recover a missing grouping-control result. The grouping/call differential can be rerun later on the clean post-fix binary.

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
