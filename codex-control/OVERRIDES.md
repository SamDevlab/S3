# Live overrides

CONTROL_REVISION: 4

No emergency stop is active.

Current direction:

- Stage 01 is complete.
- Stage 02 hosted contract qualification is recorded as PASS.
- The live Codex execution has already transitioned into Stage 04 expression lowering. Revision 4 aligns the control plane with that observed route; it does NOT retroactively fabricate Stage 03 PASS.
- Active work is Stage 04: repair and complete `stage1_expression_lowering_v2.s3` / candidate expression lowering for S1 typed values plus S2 instruction def/use.
- Do not return to Stage 03 implementation unless Stage 04 exposes a concrete regression in binding/scope resolution.
- Before the first Stage 04 implementation commit or Stage 04 exit report, backfill the Stage 03 checkpoint evidence in the report: functions, signatures, parameters, locals, loop bindings, scope resolution, shadowing, candidate Stage0 check, and exact candidate/source identity where available. Missing evidence must be reported as NOT_REOBSERVED/NOT_RECORDED, not invented as PASS.
- The current parser cleanup is legitimate Stage 04 work. Fix syntax/indentation/duplicated `match` branches narrowly, then continue semantic expression implementation rather than cycling through parser-only health checks.
- Required Stage 04 expression coverage remains: integer/negative/wide literals, identifier lookup, unary operations, arithmetic/comparison precedence, casts used by canonical Stage1, local initialization, assignment/reassignment, semantic loads/stores, instruction results, ordered O edges, exactly one R definition per instruction result.
- Every use must resolve to a defined logical value. Physical scratch indices are not semantic IDs.
- Preserve lexical shadowing semantics established by Pass1. If identifier resolution becomes ambiguous, fail closed with a reproducer rather than selecting an arbitrary binding.
- Do not emit `Z 31` during Stage 04. S3/S4/S5 are not yet complete.
- Do not over-expand fixed arrays speculatively. Measure actual candidate pressure before any capacity change.
- Before every Stage 04 implementation commit, re-fetch this control branch and acknowledge `CONTROL_REVISION=4` unless a newer revision appears.
- Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
- SELF_EMIT, Stage2, Stage3 and T4 remain unauthorized.

Required Stage 04 checkpoint:

```text
CONTROL_REVISION=4
STAGE03_EVIDENCE_BACKFILL=PASS/PARTIAL/NOT_RECORDED
EXPR_PARSER_SYNTAX=PASS/BLOCKED
INTEGER_LITERAL_LOWERING=PASS/BLOCKED
NEGATIVE_WIDE_LITERAL_LOWERING=PASS/BLOCKED
IDENTIFIER_LOOKUP=PASS/BLOCKED
LEXICAL_SHADOWING=PASS/BLOCKED
UNARY_LOWERING=PASS/BLOCKED
BINARY_PRECEDENCE=PASS/BLOCKED
COMPARISON_LOWERING=PASS/BLOCKED
LOCAL_INITIALIZATION=PASS/BLOCKED
ASSIGNMENT_REASSIGNMENT=PASS/BLOCKED
INSTRUCTION_RESULT_IDS=PASS/BLOCKED
ORDERED_OPERAND_EDGES=PASS/BLOCKED
SINGLE_RESULT_DEFINITION=PASS/BLOCKED
CANDIDATE_STAGE0_CHECK=PASS/BLOCKED
FOCUSED_NATIVE_V2_CONFORMANCE=PASS_FOR_STAGE04_FIXTURES/BLOCKED/NOT_RUN
S1_TYPED_VALUES=PASS/BLOCKED
S2_DEF_USE=PASS/BLOCKED
Z_MASK=<31
CANONICAL_SOURCE_MUTATED=NO
FIRST_REAL_BLOCKER=
NEXT_STAGE=05_CALLS_ARRAYS_S3 only if Stage04 exit gate is satisfied
```

If a Stage 04 gate fails because implementation is missing, continue implementing that slice. Do not stop merely to document the blocker. If the parser reaches a new structural error after each fix, continue narrowing and correcting the next real error, but avoid rewriting unrelated branches.

If the control-branch fetch/read fails, Codex may finish the current atomic command but must not enter a new stage, create an implementation commit, mutate canonical Stage1 or cross a promotion/bootstrap gate until the live control revision can be read again.
