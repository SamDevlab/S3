# Live overrides

CONTROL_REVISION: 5

No emergency stop is active.

Current direction:

- Stage 01 is complete.
- Stage 02 hosted contract qualification is recorded as PASS.
- The live Codex execution is in Stage 04 expression lowering. Revision 5 keeps that route active.
- Stage 03 transition was observed, but its detailed evidence must still be backfilled in the next checkpoint. Do not fabricate retrospective PASS fields.
- The current parser cleanup in `stage1_expression_lowering_v2.s3` is legitimate Stage04 work. Fix syntax/indentation/duplicated `match` branches narrowly and keep advancing the real parser/lowering.

CRITICAL OPERATOR-SCOPE CORRECTION:

The current S3 language/AST/IR does **not** have arithmetic multiplication, division, or remainder. Do not implement them as part of Stage04.

Supported current scalar operators relevant to Stage04 are:

```text
unary:  -  ~
binary: +  -  &  |  <=>  ==  !=  <  <=  >  >=
```

Subtraction follows the existing S3 architecture. `*` must not be interpreted as arithmetic multiplication. Where `*` exists for reference dereference, that is a distinct language feature and is not a Stage04 multiplication requirement.

For precedence, use repository-supported evidence such as:

```s3
mut res: trit = 1 <=> 2 < 3
```

which current V0.6 parser tests expect as `(1 <=> 2) < 3`.

- Do not return to Stage 03 implementation unless Stage 04 exposes a concrete binding/scope regression.
- Before the first Stage04 implementation commit after observing revision 5, backfill the Stage03 checkpoint evidence in the report: functions, signatures, parameters, locals, loop bindings, scope resolution, shadowing, candidate Stage0 check, and exact candidate/source identity where available. Missing evidence must remain NOT_REOBSERVED/NOT_RECORDED.
- Required Stage04 coverage: integer/negative/wide literals, identifier lookup, unary `-` and `~`, supported binary operators/precedence, actual casts used by canonical Stage1, local initialization, assignment/reassignment, semantic loads/stores, instruction results, ordered O edges and exactly one R definition for each result.
- Every use must resolve to a defined logical value. Physical scratch indices are not semantic IDs.
- Preserve lexical shadowing established by Pass1. Ambiguous lookup must fail closed with a reproducer.
- Do not emit `Z 31` during Stage04. S3/S4/S5 are incomplete.
- Do not over-expand fixed arrays speculatively. Measure actual pressure first.
- Before every Stage04 implementation commit, re-fetch this control branch and acknowledge `CONTROL_REVISION=5` unless a newer revision appears.
- Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
- SELF_EMIT, Stage2, Stage3 and T4 remain unauthorized.

Required Stage04 checkpoint:

```text
CONTROL_REVISION=5
STAGE03_EVIDENCE_BACKFILL=PASS/PARTIAL/NOT_RECORDED
EXPR_PARSER_SYNTAX=PASS/BLOCKED
INTEGER_LITERAL_LOWERING=PASS/BLOCKED
NEGATIVE_WIDE_LITERAL_LOWERING=PASS/BLOCKED
IDENTIFIER_LOOKUP=PASS/BLOCKED
LEXICAL_SHADOWING=PASS/BLOCKED
UNARY_NEGATE=PASS/BLOCKED
UNARY_INVERT=PASS/BLOCKED
SUPPORTED_BINARY_OPERATORS=PASS/BLOCKED
BINARY_PRECEDENCE=PASS/BLOCKED
COMPARISON_LOWERING=PASS/BLOCKED
LOCAL_INITIALIZATION=PASS/BLOCKED
ASSIGNMENT_REASSIGNMENT=PASS/BLOCKED
INSTRUCTION_RESULT_IDS=PASS/BLOCKED
ORDERED_OPERAND_EDGES=PASS/BLOCKED
SINGLE_RESULT_DEFINITION=PASS/BLOCKED
UNSUPPORTED_MULTIPLY_DIVIDE_REMAINDER=FAIL_CLOSED/NOT_APPLICABLE
CANDIDATE_STAGE0_CHECK=PASS/BLOCKED
FOCUSED_NATIVE_V2_CONFORMANCE=PASS_FOR_STAGE04_FIXTURES/BLOCKED/NOT_RUN
S1_TYPED_VALUES=PASS/BLOCKED
S2_DEF_USE=PASS/BLOCKED
Z_MASK=<31
CANONICAL_SOURCE_MUTATED=NO
FIRST_REAL_BLOCKER=
NEXT_STAGE=05_CALLS_ARRAYS_S3 only if Stage04 exit gate is satisfied
```

If a Stage04 gate fails because implementation is missing, continue implementing that slice. Do not stop merely to document the blocker. If parser repair reveals the next structural error, fix that next real error without rewriting unrelated branches.

If the control-branch fetch/read fails, Codex may finish the current atomic command but must not enter a new stage, create an implementation commit, mutate canonical Stage1 or cross a promotion/bootstrap gate until the live control revision can be read again.
