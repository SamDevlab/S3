# Live overrides

CONTROL_REVISION: 14

No emergency stop is active.

## Current direction

- Stage 04 remains accepted for transition as `PASS_REPORTED_PENDING_REMOTE_BACKFILL`; preserve/push the local Stage04 checkpoint on the next implementation commit without fabricating remote evidence.
- Stage 05 remains active under paired engineering mode.
- Automatic stage advance remains disabled.
- Finish the already in-flight `current_code == 2` right-parenthesis diagnostic build before applying any new repair.
- For the current Stage05 campaign, use `codex-control/STAGE05_COMMAND_CARD.md` as the short operational entry point after reading `CURRENT.json` and this file.
- Use `codex-control/STAGE05_TRIAGE_DECISION_TABLE.json` to classify the close probe and `codex-control/STAGE05_POSTFIX_REGRESSION_MATRIX.json` for post-fix same-binary regression order.

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

## Fast path after the eventual repair

Do not waste a native build per fixture.

1. regenerate clean candidate;
2. `s3 check` once;
3. record candidate SHA256;
4. build one Linux native binary;
5. record binary SHA256;
6. reuse the same binary through the unlocked fixtures in `STAGE05_POSTFIX_REGRESSION_MATRIX.json`;
7. stop at the first unexpected parser/semantic/mask result;
8. run strict Stage05 conformance immediately on the first valid internal call before another source edit;
9. emit a paired checkpoint.

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
