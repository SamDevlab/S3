# Live overrides

CONTROL_REVISION: 10

No emergency stop is active.

## Current direction

- Stage 01 is complete.
- Stage 02 hosted contract qualification is recorded as PASS.
- Stage 03 missing detailed evidence remains backfill debt.
- Stage 04 remains accepted for transition as `PASS_REPORTED_PENDING_REMOTE_BACKFILL`; preserve/push `reports/selfhost/stage1/STAGE04_CHECKPOINT_20260827.md` on the next implementation commit without fabricating missing remote evidence.
- Stage 05 is the active implementation stage.
- Paired engineering mode remains mandatory.
- Read `codex-control/STAGE05_CALL_PARSE_DIAGNOSIS.md` before the next Stage05 edit.
- Automatic stage advance remains disabled.

## Latest paired diagnosis

The latest live Codex instrumentation localized the first Stage05 blocker:

```text
simple helper expression: parse_ok=-1 at parser checkpoint
helper(1):               parse_ok=0 at parser checkpoint
failure phase:           PARSER
failure before eval:     YES
```

Therefore the first proven blocker is now:

```text
VALID_INTERNAL_CALL_REJECTED_DURING_PARSER_PHASE
```

Do not keep instrumenting evaluation, `C/A`, arrays, or foreign calls until valid call parsing is repaired.

Candidate/binary SHA256 were not present in the supplied checkpoint and remain required backfill. Do not invent them.

## Immediate repair slice

The repository parser treats a call as postfix syntax: parse the callee primary, recognize `(` as a call opener, parse arguments as expressions, and consume the matching `)` once in the call closer.

For `helper(1)` inspect, in this order:

1. **call-vs-grouping classification** — `(` following an identifier/primary must open a call frame rather than generic grouping;
2. **argument stop predicate** — `)` at the active call-frame depth must end the argument/call rather than be classified as an invalid expression token;
3. **right-paren bookkeeping** — close/decrement the call parenthesis exactly once and do not fall through into a second generic `)` rejection;
4. **call-frame restoration** — clear/restore call-pending, callee and argument state without changing `parse_ok`.

Earlier work already found `paren_count` placement defects, so inspect the right-paren path carefully, but do not assume it is the cause until the exact branch is shown.

## Required next sequence

1. statically inspect the generated candidate around call-open, argument stop and call-close;
2. identify one exact branch that sets or propagates `parse_ok=0` for `helper(1)`;
3. patch only that branch in `tools/patch_stage1_calls_arrays_s3.py`;
4. regenerate the clean candidate and remove temporary diagnostic output;
5. run `s3 check` on that exact candidate;
6. record exact candidate SHA256;
7. perform one native Linux build and record binary SHA256;
8. rerun the same minimal internal-call fixture;
9. run strict Stage05 conformance for that fixture;
10. emit a paired checkpoint and stop before broadening.

If static inspection still cannot identify the exact branch, one additional diagnostic build is allowed. Trace only the tokens around `helper`, `(`, `1`, `)` with token kind, call-frame mode/flag, parenthesis depth, argument ordinal and `parse_ok`. No broad trace.

## First internal-call success boundary

Require:

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

Call records must preserve:

- ordered `O` operands;
- `R` result when applicable;
- `C` with callee kind `1`, resolved internal function id, exact ASCII callee span, argument count and result count;
- ordered `A` arguments matching the same semantic values as CALL `O` operands;
- reusable logical result identity independent of physical scratch/pool slots.

`Z 31` remains forbidden until S4/S5 close. Invalid/unresolved calls may fail closed with `Z 0`, but valid `helper(1)` may not.

## Expansion order after the first call passes

Only then:

1. zero-argument internal call;
2. ordered multiple arguments;
3. nested call;
4. call result reuse;
5. unresolved callee fail-closed;
6. foreign resolution/signature;
7. fixed-array/index load/store required by canonical Stage1.

Do not implement arrays while the valid internal-call parser blocker remains unresolved.

## Capacity policy

Historical `736 required / 746 capacity` call-pool evidence is provenance only. Measure exact current pressure before changing capacity. Semantic `A` edges and logical values are not physical pool slots.

## Authorization boundary

Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
SELF_EMIT remains unauthorized.
Stage2 remains unauthorized.
Stage3 remains unauthorized.
T4 remains unauthorized.
Stage06 remains unauthorized.

If the control branch cannot be read, Codex may finish only the current atomic command. Do not create a new implementation commit, begin another stage, mutate canonical Stage1, or cross any bootstrap/promotion gate until the live revision is readable again.
