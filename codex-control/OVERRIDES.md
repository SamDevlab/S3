# Live overrides

CONTROL_REVISION: 6

No emergency stop is active.

Current direction:

- Stage 01 is complete.
- Stage 02 hosted contract qualification is recorded as PASS.
- Stage 03 transition was observed; detailed evidence remains backfill debt where not re-observed.
- Stage 04 remains the active implementation stage.
- Revision 6 does **not** broaden Stage04 and does not authorize any later stage. It adds the closure fast path in `codex-control/STAGE04_FAST_PATH.md`.
- Finish any currently running Stage0/native build/probe/test process before applying this revision. Do not duplicate an in-flight gate.
- After the current numeric-cast proof finishes, follow `STAGE04_FAST_PATH.md` in order: supported casts -> fixed regression matrix -> exact Stage0 check -> focused Stage04 tests -> representative strict S3IR2 conformance -> full focused Stage04 checkpoint.
- Fix one first real blocker per cycle. Do not make multiple speculative repairs from one failed run.
- Do not repeatedly re-check SSH, Linux/Python/cc, PR OPEN/DRAFT state, or already-proven function/block discovery unless a new execution failure implicates them.

CRITICAL OPERATOR-SCOPE RULE:

The current S3 language/AST/IR does **not** have arithmetic multiplication, division, or remainder as Stage04 requirements.

Supported current scalar operators relevant to Stage04 are:

```text
unary:  -  ~
binary: +  -  &  |  <=>  ==  !=  <  <=  >  >=
casts:  to_i64(x)  to_f64(x)  to_tryte(x)
```

Subtraction follows the existing S3 architecture. Unsupported `*`, `/`, `%` must remain fail-closed and produce no arithmetic opcode. Do not reinterpret reference dereference as multiplication.

Stage04 semantic requirements remain:

- integer, negative and wide literals;
- identifier lookup and lexical shadowing;
- supported unary/binary operators and precedence;
- numeric casts used by canonical Stage1;
- local initialization;
- assignment/reassignment;
- semantic loads/stores;
- instruction result IDs;
- ordered O edges;
- exactly one R definition for each result;
- every use resolves to a defined logical value;
- logical semantic IDs remain independent from physical storage/scratch indices.

Completeness boundary:

- `Z 3` is the expected successful Stage04-only completeness mask.
- `Z 0` is appropriate for unsupported/fail-closed fixtures.
- Do not emit `Z 31` in Stage04; S3/S4/S5 are incomplete.

Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
SELF_EMIT, Stage2, Stage3 and T4 remain unauthorized.

Required Stage04 checkpoint:

```text
CONTROL_REVISION=6
STAGE03_EVIDENCE_BACKFILL=PASS/PARTIAL/NOT_RECORDED/NOT_REOBSERVED
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
NUMERIC_CASTS_USED_BY_STAGE1=PASS/BLOCKED
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
Z_MASK=3
CANONICAL_SOURCE_MUTATED=NO
FIRST_REAL_BLOCKER=
NEXT_STAGE=05_CALLS_ARRAYS_S3 only if Stage04 exit gate is satisfied and the live control plane still permits automatic advance
```

If strict conformance fails, preserve one smallest representative mismatch and correct that semantic slice before broadening tests. A constant-fold-only difference must not be confused with a semantic mismatch; use parameter/local fixtures where needed to compare the preserved semantics.

If the control-branch fetch/read fails, Codex may finish the current atomic command but must not enter a new stage, create an implementation commit, mutate canonical Stage1 or cross a promotion/bootstrap gate until the live control revision can be read again.
