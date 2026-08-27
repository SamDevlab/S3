# Live overrides

CONTROL_REVISION: 16

No emergency stop is active.

## Current direction

- Stage 04 remains accepted for transition as `PASS_REPORTED_PENDING_REMOTE_BACKFILL`; preserve/push the local Stage04 checkpoint on the next implementation commit without fabricating remote evidence.
- Stage 05 remains active under paired engineering mode.
- Automatic stage advance remains disabled.
- Finish the already in-flight `current_code == 2` right-parenthesis diagnostic build before applying any new repair.
- Use `codex-control/STAGE05_COMMAND_CARD.md` as the short operational entry point after reading `CURRENT.json` and this file.
- Use exact UTF-8/LF fixtures under `codex-control/fixtures/stage05/` and verify hashes against `MANIFEST.json`.
- Use `codex-control/STAGE05_TRIAGE_DECISION_TABLE.json` for the close probe and `codex-control/STAGE05_CONFORMANCE_EXPECTATIONS.md` for the first strict-verifier mismatch after parser repair.

## Current blocker

```text
VALID_INTERNAL_CALL_REJECTED_AT_OR_AROUND_RIGHT_PAREN_CALL_CLOSE
```

Observed facts remain:

```text
valid internal call -> Z 0
C structurally emitted
A structurally emitted
failure phase -> parser before evaluation
RIGHT_PAREN token code -> 2
owning diagnostic branch -> current_code == 2
```

The grouping-control result remains `NOT_REPORTED`; do not infer it.

## Finish the in-flight close probe only

Capture:

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

Then regenerate the candidate cleanly and remove temporary diagnostics.

Classification:

```text
BEFORE false
  -> ARGUMENT_STOP_OR_TOKEN_BEFORE_RIGHT_PAREN

BEFORE valid, AFTER false
  -> RIGHT_PAREN_CALL_CLOSE

BEFORE valid, AFTER valid, final Z 0
  -> POST_PARSE_FINALIZATION_OR_COMPLETENESS
```

Patch one proven owning condition only.

## Fast path after parser repair

1. regenerate clean candidate;
2. `s3 check` once;
3. record candidate SHA256;
4. build one Linux native binary;
5. record binary SHA256;
6. run exact `internal_one_arg_call.s3` first;
7. if parser valid, run strict Stage05 conformance immediately;
8. preserve verifier JSON and use only `errors[0]`;
9. classify via `STAGE05_CONFORMANCE_EXPECTATIONS.md`;
10. fix one owner only;
11. when strict conformance passes, reuse the same binary through unlocked fixtures in `STAGE05_POSTFIX_REGRESSION_MATRIX.json` until the first unexpected result.

Authoritative verifier error owners are already mapped for:

```text
CALL instruction shape
O/value mapping
R result edge
C record attachment
C metadata
C source span
A argument mapping
```

Do not rebuild between fixtures while candidate source/hash is unchanged.

The first valid internal call requires exact S1+S2+S3 semantics and `Z 7`. `Z 31` remains forbidden until S4/S5 close.

## Time-saving prohibitions

Do not re-run or revisit these unless a new failure directly implicates them:

- SSH/Linux/Python/cc qualification;
- PR OPEN/DRAFT state;
- Stage04 expression matrix;
- function/block discovery;
- historical 736/746 capacity;
- foreign calls;
- arrays;
- Stage06 or later.

## Authorization boundary

Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
SELF_EMIT remains unauthorized.
Stage2 remains unauthorized.
Stage3 remains unauthorized.
T4 remains unauthorized.
Stage06 remains unauthorized.
