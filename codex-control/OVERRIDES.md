# Live overrides

CONTROL_REVISION: 18

No emergency stop is active.

## Current direction

- Stage 04 remains accepted for transition as `PASS_REPORTED_PENDING_REMOTE_BACKFILL`.
- Stage 05 remains active under paired engineering mode.
- Automatic stage advance remains disabled.
- The special-open legacy-dispatch bug was a real first setter and its guard must be preserved, but post-guard evidence proves another residual blocker remains.
- Read `codex-control/STAGE05_RESIDUAL_PARSE_TRANSITION.md` before the next permanent source edit.
- Finish only the already-started token-trace build on the guarded candidate. Do not start another build or repair before it terminates.

## New post-guard evidence

```text
special-open guard applied
internal call still structurally recognized
C emitted
A emitted
helper()  -> Z 0
helper(1) -> Z 0
```

Therefore the old blocker is retained as a fixed/partial cause, not the current owner:

```text
PRIOR_CAUSE=SYNTHETIC_CALL_OPEN_KIND_FALLS_THROUGH_LEGACY_OPERAND_DISPATCH
CURRENT_BLOCKER=POST_SPECIAL_OPEN_RESIDUAL_PARSE_OK_SETTER_COMMON_TO_ZERO_AND_ONE_ARG
```

Because zero- and one-argument calls both fail, do not prioritize argument parsing or one-argument arity logic unless the new trace proves it.

## Atomic task

Capture the FIRST `parse_ok` transition from valid `-1` to invalid `0` on the already-guarded candidate.

Preserve token order and, when available, these fields:

```text
TOKEN_INDEX=
TOKEN_CODE=
CURRENT_KIND=
PARSE_OK_BEFORE=
PARSE_OK_AFTER=
STAGE05_SPECIAL_OPEN=
CALL_FRAME_ACTIVE=
PAREN_DEPTH=
OP_COUNT=
ARG_COUNT=
HAS_ARG=
```

Use the actual marker/variable names if different.

## Classification

If the first flip is still on the synthetic special-open token:

```text
NEXT_OWNER=SPECIAL_OPEN_GUARD_COVERAGE
```

If parsing remains valid until the matching `)` and flips while closing both zero- and one-arg calls:

```text
NEXT_OWNER=CALL_CLOSE_COMMON_STATE
```

If `)` closes valid and the flip occurs later in the same token cycle:

```text
NEXT_OWNER=POST_CALL_FALLTHROUGH_OR_FRAME_RESTORE
```

If parser state never flips but final output remains `Z 0`:

```text
NEXT_OWNER=STAGE05_COMPLETENESS_OR_CONFORMANCE
```

In that case stop parser instrumentation and run strict conformance/completeness on a clean candidate.

## After the trace

1. preserve raw trace and exact hashes if available;
2. regenerate cleanly to remove diagnostics;
3. patch one proven owner only;
4. `s3 check` once;
5. build once;
6. run exact pinned zero-arg and one-arg fixtures on the same binary;
7. stop on the first unexpected result;
8. when parser is valid, run strict Stage05 conformance immediately and consume `errors[0]` only.

## Do not reopen

Unless new evidence contradicts it, do not revisit:

- the `stage05_open_kind > 0` truth-branch experiment;
- callee recognition;
- basic `C/A` structural emission;
- Stage04 expression matrix;
- SSH/Linux/Python/cc qualification;
- arrays;
- foreign calls;
- Stage06 or later.

## Authorization boundary

Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
SELF_EMIT remains unauthorized.
Stage2 remains unauthorized.
Stage3 remains unauthorized.
T4 remains unauthorized.
Stage06 remains unauthorized.
