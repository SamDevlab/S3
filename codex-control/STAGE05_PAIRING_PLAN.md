# Stage05 paired engineering plan

Purpose: close S3 call dataflow in small, jointly-reviewed slices before broadening into foreign calls and arrays.

This file does not authorize canonical Stage1 mutation, SELF_EMIT, Stage2, Stage3, T4, or Stage06.

## Entry evidence

Stage04 transition is accepted from the user-supplied live Codex checkpoint as `PASS_REPORTED_PENDING_REMOTE_BACKFILL` because the reported exact candidate demonstrated:

- focused Stage04 tests PASS;
- strict semantic conformance 10/10 on the preserved representative fixtures;
- full native Stage04 operator/cast/regression matrix PASS;
- supported fixtures emitted `Z 3`;
- unsupported `* / %` and invalid casts failed closed with `Z 0`;
- deterministic candidate generation was observed twice with the same SHA256;
- canonical source remained unmodified.

The local `reports/selfhost/stage1/STAGE04_CHECKPOINT_20260827.md` must be preserved and pushed/backfilled when Codex next creates an implementation commit. Do not fabricate missing remote evidence.

## Current first blocker

Codex has already produced a Stage05 candidate that structurally emits function/call/value/instruction lanes including `C` and `A`, but the current internal parser state falls to `parse_ok=0`, resulting in `Z 0`.

The immediate task is not to add more features. Locate the first exact transition where `parse_ok` becomes false.

### Finish the in-flight diagnostic first

1. Confirm the already-built `/tmp/s3-stage05-debug` binary exists.
2. Record its SHA256 and candidate source SHA256.
3. Run the same minimal internal-call fixture used for the current diagnosis.
4. Capture the three temporary diagnostic points already inserted:
   - after RPN parsing;
   - after expression/call evaluation;
   - final closeout.
5. Report the first point whose value differs from the preceding point.
6. Regenerate the clean candidate immediately after extracting the diagnosis so temporary diagnostics do not become implementation state.

Do not start a second native compilation while the existing diagnostic process is still unresolved.

## First semantic slice: one internal call

Close exactly one simple internal call before zero-arg, nested, foreign, or arrays.

Recommended fixture shape:

```s3
fn add(a: i64, b: i64) -> i64:
    return a + b

fn main() -> i64:
    return add(7, 8)
```

Stage05 call semantics must preserve:

- CALL instruction opcode `14`;
- ordered instruction operands through `O`;
- one instruction result through `R` when the call returns one value;
- `C instruction_id callee_kind callee_function_id callee_name_start callee_name_length argument_count result_count`;
- one `A instruction_id ordinal value_id` for every argument, in source order;
- internal callee kind `1`;
- resolved internal `callee_function_id`;
- exact ASCII callee source span;
- argument values in `A` matching the same semantic values used by the CALL instruction `O` edges;
- call result `R` usable by the enclosing return/local instruction without changing logical identity.

The frozen oracle serializes calls after `I/O/R`; candidate record ordering must remain deterministic.

## Stage05 completeness boundary

When S1 + S2 + S3 are proven for a call fixture, the stage-appropriate completeness mask is:

```text
Z 7
```

because `1 | 2 | 4 = 7`.

`Z 31` is forbidden until S4/S5 are also complete. `Z 0` remains appropriate for unresolved/invalid fail-closed fixtures.

Do not mistake a verifier implementation that expects final `Z 31` for a Stage05 semantic failure; use the stage-aware diagnostic/conformance path while still requiring exact S1/S2/S3 semantics.

## One blocker per cycle

After the `parse_ok` transition is located:

1. fix only the owning slice;
2. run `s3 check` on the exact generated candidate;
3. rebuild one native binary;
4. rerun the same internal-call fixture;
5. run strict semantic conformance for that fixture;
6. emit a `PAIRING_CHECKPOINT`;
7. stop and re-read control before broadening.

Do not combine a `parse_ok` fix with array support, foreign resolution, capacity expansion, or unrelated parser cleanup.

## Expansion order after the first internal call passes

Only after the internal call fixture is conformant:

1. zero-argument internal call;
2. ordered multi-argument internal call;
3. nested call;
4. call-result reuse;
5. unresolved internal callee fail-closed;
6. foreign call/signature resolution;
7. only then fixed-array/index load/store semantics.

## Capacity rule

Historical `736 required / 746 capacity` call-argument evidence is provenance only. Do not reuse or resize from those numbers without measuring the exact current candidate/source pressure. Semantic IDs and `A` edges are not physical pool slots.

## Required paired checkpoint for the current blocker

```text
PAIRING_CHECKPOINT_BEGIN
CONTROL_REVISION=9
ACTIVE_STAGE=05_CALLS_ARRAYS_S3
CANDIDATE_SOURCE_SHA256=<64 hex>
NATIVE_BINARY_SHA256=<64 hex>
FIXTURE=<minimal internal call fixture>
COMMAND_CLASS=STAGE05_PARSE_OK_DIAGNOSTIC
STATUS=PASS/FAIL/BLOCKED
PARSE_OK_AFTER_RPN=<value>
PARSE_OK_AFTER_EVAL=<value>
PARSE_OK_FINAL=<value>
Z_MASK=<integer>
STRICT_CONFORMANCE=PASS/FAIL/NOT_RUN
MAPPED_VALUES=<integer or NOT_RUN>
FIRST_REAL_BLOCKER=<single exact blocker>
CANONICAL_SOURCE_MUTATED=NO
SELF_EMIT_EXECUTED=NO
STAGE2_CREATED=NO
STAGE3_CREATED=NO
T4_EXECUTED=NO
PAIRING_CHECKPOINT_END
```

ChatGPT will use this checkpoint to select the next single repair slice.