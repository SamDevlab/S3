# Stage05 internal-call parser diagnosis

Purpose: narrow the current Stage05 blocker after the live Codex instrumentation proved that `parse_ok` becomes false while parsing a real call expression, before call evaluation/final closeout.

This document is diagnostic guidance only. It does not authorize canonical mutation, Stage06, SELF_EMIT, Stage2, Stage3, or T4.

## Observed evidence

From the live Codex diagnostic supplied by the user:

- the Linux guest and native build path are operational;
- the instrumented Stage05 candidate builds natively;
- a simple expression in `helper` reaches the parser checkpoint with `parse_ok=-1`;
- the call expression `helper(1)` reaches the corresponding parser checkpoint with `parse_ok=0`;
- therefore the first proven failure is in parsing the call expression, before expression/call evaluation;
- existing `I/O/R/C/A` structure is not the first blocker for this fixture.

Candidate/binary hashes were not present in the supplied checkpoint, so they remain required backfill and must not be invented.

## Authoritative parser behavior to preserve

The repository parser treats a call as postfix syntax:

1. parse a primary expression/callee;
2. when `(` immediately follows that expression, enter call parsing rather than generic grouping;
3. parse zero or more argument expressions;
4. comma separates arguments at the current call-frame depth;
5. `)` terminates the call argument list and is consumed exactly once by the call closer;
6. the resulting call expression may itself participate in further postfix/infix parsing.

For the minimal source `helper(1)`, the semantic token lifecycle is therefore:

```text
IDENTIFIER(helper)
LEFT_PAREN   -> open CALL frame
INTEGER(1)   -> parse argument expression
RIGHT_PAREN  -> close CALL frame exactly once
END-OF-EXPR  -> parser remains valid
```

A call parenthesis must not simultaneously be treated as a generic grouping parenthesis.

## Ranked candidate failure modes

Inspect these in order. Do not patch multiple hypotheses at once.

### 1. Call-vs-grouping classification

When an identifier/primary is followed by `(`, verify that the candidate opens a call frame before generic grouping logic can consume the same token.

Failure signature:

- `helper` alone parses;
- `helper(1)` fails during parser phase;
- argument token itself is otherwise valid.

### 2. Right-parenthesis close bookkeeping

Verify that the matching `)`:

- closes the active call frame exactly once;
- decrements any shared parenthesis depth exactly once;
- does not fall through into a generic `)` rejection path after call closure.

Earlier Stage05 work already exposed `paren_count` placement issues, so this is a high-probability inspection point, but it is still a hypothesis until the owning condition is shown.

### 3. Argument stop predicate

Inside a call argument expression, `RIGHT_PAREN` at the call frame depth must mean "argument/call complete", not "unexpected token".

For multi-argument calls later, `COMMA` at the same depth must mean "argument complete". Nested parentheses/calls must not trigger this stop until their inner depth closes.

### 4. Call-frame state restoration

After closing `helper(1)`, verify that temporary state such as call-pending/callee index/argument ordinal/parenthesis mode is restored without setting `parse_ok=0`.

## Required next repair slice

Before another broad native matrix:

1. inspect the generated candidate code around call-open, argument stop, and call-close paths;
2. identify one exact conditional/branch that sets or propagates `parse_ok=0` for `helper(1)`;
3. patch only that branch in `tools/patch_stage1_calls_arrays_s3.py`;
4. regenerate the clean candidate, removing temporary diagnostic output;
5. run `s3 check`;
6. build one native candidate;
7. rerun only the same minimal internal-call fixture;
8. require parser validity through closeout and Stage05 semantic conformance.

If static inspection cannot identify the exact branch, one additional diagnostic build is allowed, but instrument only the token transitions around `helper`, `(`, `1`, `)` with: token kind, call-frame flag/mode, parenthesis depth, argument ordinal, and `parse_ok`. Do not add broad tracing.

## Success boundary for this slice

For one valid internal call after the parser repair:

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

If parser validity is restored but strict conformance reports a semantic mismatch, stop on the first mismatch and hand it back through the paired checkpoint. Do not broaden into foreign calls or arrays yet.

## Negative boundary

An unresolved/invalid call may fail closed with `Z 0`, but the valid `helper(1)` fixture must not use fail-closed behavior as a substitute for implementing valid call parsing.
