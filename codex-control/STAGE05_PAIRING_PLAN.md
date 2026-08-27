# Stage05 paired engineering plan

Purpose: close S3 call dataflow in small, jointly reviewed slices before foreign calls and arrays.

This file does not authorize canonical Stage1 mutation, SELF_EMIT, Stage2, Stage3, T4, or Stage06.

## Entry evidence

Stage04 transition remains accepted as `PASS_REPORTED_PENDING_REMOTE_BACKFILL` from the live Codex evidence supplied by the user: focused tests PASS, strict representative conformance 10/10 PASS, full native Stage04 matrix PASS, supported fixtures `Z 3`, unsupported fixtures `Z 0`, deterministic candidate generation reported, canonical source unmodified.

The local `reports/selfhost/stage1/STAGE04_CHECKPOINT_20260827.md` still requires remote backfill on the next implementation commit.

## Current first blocker — revision 10

The diagnostic phase is complete enough to localize the first Stage05 failure:

```text
helper simple expression -> parser checkpoint parse_ok=-1
helper(1)                -> parser checkpoint parse_ok=0
FIRST_FAILURE_PHASE      -> PARSER
EVALUATION_FIRST_BLOCKER -> NO
```

Read `codex-control/STAGE05_CALL_PARSE_DIAGNOSIS.md`.

Do not add foreign calls, arrays, capacity changes, or broad parser cleanup while this blocker is open.

## Current single repair slice

Repair valid postfix call parsing for one internal one-argument call.

Inspect only:

1. call-vs-grouping classification at `identifier + (`;
2. call argument stop on `)` at the active call depth;
3. exact once-only `)`/parenthesis-depth bookkeeping;
4. call-frame state restoration.

The authoritative parser behavior is: primary callee -> postfix `(` -> parse argument expression(s) -> consume `)` once -> return call expression.

If static inspection identifies the exact condition, patch it directly. Otherwise one narrow diagnostic build may trace only `helper`, `(`, `1`, `)` with token kind, call-frame mode, parenthesis depth, argument ordinal, and `parse_ok`.

## Required repair sequence

1. identify one exact parser branch that owns the false transition;
2. patch only that branch in `tools/patch_stage1_calls_arrays_s3.py`;
3. regenerate a clean candidate with no temporary diagnostics;
4. `s3 check` exact candidate;
5. record candidate SHA256;
6. one native Linux build;
7. record binary SHA256;
8. rerun the same minimal internal-call fixture;
9. strict Stage05 conformance;
10. emit paired checkpoint and stop before broadening.

## First semantic slice: one internal call

Recommended fixture:

```s3
fn helper(value: i64) -> i64:
    return value

fn main() -> i64:
    return helper(1)
```

Call semantics must preserve:

- CALL instruction opcode `14`;
- ordered instruction operands through `O`;
- one result through `R` when the call returns one value;
- `C instruction_id callee_kind callee_function_id callee_name_start callee_name_length argument_count result_count`;
- internal callee kind `1`;
- resolved internal function id;
- exact ASCII callee source span;
- one ordered `A` edge per argument;
- `A` argument values matching the same semantic values as CALL `O` operands;
- call result `R` usable by enclosing return/local lowering without changing logical identity.

## Stage05 completeness boundary

When S1 + S2 + S3 are proven:

```text
Z 7
```

because `1 | 2 | 4 = 7`.

`Z 31` is forbidden until S4/S5 close. Invalid/unresolved call fixtures may use `Z 0` fail-closed; valid `helper(1)` may not.

## Expansion order after first internal call passes

1. zero-argument internal call;
2. ordered multi-argument internal call;
3. nested call;
4. call-result reuse;
5. unresolved callee fail-closed;
6. foreign call/signature resolution;
7. fixed-array/index load/store semantics.

## Capacity rule

Historical `736 required / 746 capacity` evidence is provenance only. Do not reuse or resize from those values without exact current measurement. Semantic IDs and `A` edges are not physical pool slots.

## Required paired checkpoint

```text
PAIRING_CHECKPOINT_BEGIN
CONTROL_REVISION=10
ACTIVE_STAGE=05_CALLS_ARRAYS_S3
CANDIDATE_SOURCE_SHA256=<64 hex>
NATIVE_BINARY_SHA256=<64 hex>
FIXTURE=<minimal internal call fixture>
COMMAND_CLASS=STAGE05_INTERNAL_CALL_PARSE_REPAIR
STATUS=PASS/FAIL/BLOCKED
PARSE_OK_AFTER_RPN=<value>
PARSE_OK_AFTER_EVAL=<value>
PARSE_OK_FINAL=<value>
CALL_OPCODE_14=PASS/FAIL/NOT_RUN
C_RECORD=PASS/FAIL/NOT_RUN
A_ORDER=PASS/FAIL/NOT_RUN
O_ORDER=PASS/FAIL/NOT_RUN
R_RESULT=PASS/FAIL/NOT_RUN
Z_MASK=<integer>
STRICT_CONFORMANCE=PASS/FAIL/NOT_RUN
MAPPED_VALUES=<integer or NOT_RUN>
FIRST_REAL_BLOCKER=<single exact blocker or NONE>
CANONICAL_SOURCE_MUTATED=NO
SELF_EMIT_EXECUTED=NO
STAGE2_CREATED=NO
STAGE3_CREATED=NO
T4_EXECUTED=NO
PAIRING_CHECKPOINT_END
```

ChatGPT will use the checkpoint to select the next single Stage05 slice.
