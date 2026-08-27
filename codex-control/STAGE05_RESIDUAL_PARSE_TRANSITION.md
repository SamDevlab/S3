# Stage05 residual parse transition — paired trace

Purpose: consume the post-guard evidence without reopening already-proven Stage05 work.

## What is already established

The narrow `stage05_special_open` guard was applied to the legacy operand rejection path. After that repair:

- internal call structure is still recognized;
- `C` and `A` records are emitted;
- `helper(1)` still ends with `Z 0`;
- `helper()` also ends with `Z 0`.

Therefore the special-open legacy-dispatch bug was real but not the only remaining Stage05 parser/state blocker.

The zero-argument failure is important: do not classify the remaining failure as argument-expression parsing or one-argument arity logic unless a new trace directly proves that.

## Current blocker

```text
POST_SPECIAL_OPEN_RESIDUAL_PARSE_OK_SETTER_COMMON_TO_ZERO_AND_ONE_ARG
```

## Current atomic task

Finish only the already-started token trace on the guarded candidate. Do not start another build or source repair before that trace reaches terminal state.

Use an exclusive diagnostic marker and preserve raw token order. The useful fields are:

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

Use actual existing variable names when they differ. The key evidence is the FIRST observed `parse_ok` transition from valid (`-1`) to invalid (`0`).

If possible with the existing instrumentation, report both `helper()` and `helper(1)` from the same unchanged debug binary. Do not rebuild solely to obtain the second case.

## Classification

### A — guard incomplete

If the first `-1 -> 0` still occurs on the synthetic special-open token while `stage05_special_open` is active:

```text
NEXT_OWNER=SPECIAL_OPEN_GUARD_COVERAGE
```

Repair only the exact unguarded legacy rejection setter. Do not broaden to global punctuation handling.

### B — call close

If parse state remains valid through call-open/arguments and flips while consuming the matching `)` for both zero- and one-argument calls:

```text
NEXT_OWNER=CALL_CLOSE_COMMON_STATE
```

Inspect only common call-frame close bookkeeping: single depth decrement, frame pop/restore, operator marker removal, or generic right-paren fallthrough. Arity-specific logic is not the primary suspect because zero- and one-argument forms both fail.

### C — post-call same-cycle fallthrough

If `)` closes with `parse_ok=-1` and the first flip occurs later in the same token cycle:

```text
NEXT_OWNER=POST_CALL_FALLTHROUGH_OR_FRAME_RESTORE
```

Check whether the just-consumed call token/frame falls through into generic operand/operator rejection or restores stale expression state.

### D — parser stays valid but Z is 0

If no `parse_ok` transition occurs and parser remains valid through expression close, but final output is still `Z 0`:

```text
NEXT_OWNER=STAGE05_COMPLETENESS_OR_CONFORMANCE
```

Stop parser instrumentation. Regenerate cleanly and run strict Stage05 conformance / completeness accounting. Do not patch parser again without evidence.

## After the first proven transition

1. preserve raw trace and exact debug binary/candidate hashes if available;
2. regenerate cleanly to remove diagnostics;
3. repair one owner only;
4. `s3 check` once;
5. build one native binary;
6. run exact pinned `internal_one_arg_call.s3` and `zero_arg_internal_call.s3` on that same binary;
7. stop at the first unexpected result;
8. if parser is valid, run strict conformance immediately and consume `errors[0]` only.

## Do not reopen

Unless new evidence directly contradicts it, do not revisit:

- the `stage05_open_kind > 0` truth-branch experiment;
- callee recognition;
- `C/A` structural emission;
- Stage04 expression lowering;
- SSH/toolchain qualification;
- arrays;
- foreign calls;
- Stage06 or later.

Canonical mutation, SELF_EMIT, Stage2, Stage3 and T4 remain unauthorized.
