# Stage04 closure fast path

Purpose: shorten the final Stage04 feedback loop without changing Stage04 scope or authorization.

This file is operational guidance only. It does not authorize canonical Stage1 mutation, SELF_EMIT, Stage2, Stage3 or T4.

## Entry condition

Use this fast path only while the live control plane still selects `04_EXPRESSIONS_S1_S2`.

If an existing Stage0 check, Linux build, native run, pytest process or diagnostic probe is already running, let that exact process reach a terminal result first. Do not duplicate it.

## Current closure order

Do not restart broad parser exploration. Close Stage04 in this order:

1. Finish the current numeric-cast rebuild/proof.
2. Prove exactly these supported casts first:
   - `to_i64(x)`
   - `to_f64(x)`
   - `to_tryte(x)`
   - one invalid/unsupported cast form must fail closed.
3. Rerun the previously working regression matrix on the same rebuilt native candidate:
   - literal
   - negative/wide literal
   - parameter
   - local
   - immutable local initialization
   - mutable local initialization
   - reassignment
   - unary `-`
   - unary `~`
   - `+`
   - `-`
   - `&`
   - `|`
   - `<=>`
   - `== != < <= > >=`
   - precedence fixture
   - unsupported `* / %` => fail closed / `Z 0`
4. Run Stage0 check once on the exact candidate source used for the native matrix.
5. Run the focused Stage04 tests only. Exclude historical canonical-SHA identity checks whose input was already dirty before this campaign; record them as historical/preexisting rather than silently dropping them.
6. Run strict S3IR2 v2 conformance on a small representative matrix that avoids constant-fold-only mismatches where appropriate:
   - parameter identity
   - local identity
   - parameter + parameter
   - parameter - parameter
   - unary over parameter/local
   - comparison over parameter/local
   - mutable initialization/reassignment
   - each supported numeric cast
7. If strict conformance exposes a mismatch, preserve exactly one first real mismatch and fix that semantic slice before running a broader matrix.
8. Only after the representative strict matrix passes, run the full Stage04 focused matrix and produce the Stage04 checkpoint.

## One blocker per cycle

When a command fails:

- capture the exact command, exit status and first actionable traceback/mismatch;
- classify it as environment, parser, binding, value/type, def/use, operator/cast, native transport, historical identity, or conformance;
- fix only that first real blocker;
- rerun the smallest command that proves the fix;
- then resume this sequence from the nearest required regression point.

Do not create multiple speculative repairs from one failing run.

## Stop repeating already-proven infrastructure

Unless a failure points back to it, do not repeatedly re-prove:

- SSH availability;
- Python/cc availability;
- PR OPEN/DRAFT status;
- function discovery that already produces `F` records;
- basic block discovery that already produces `B` records;
- native build capability itself.

Recheck infrastructure only when an execution error actually implicates it.

## Required semantic boundary

Stage04 may close only when the exact candidate demonstrates:

```text
EXPR_PARSER_SYNTAX=PASS
INTEGER_LITERAL_LOWERING=PASS
NEGATIVE_WIDE_LITERAL_LOWERING=PASS
IDENTIFIER_LOOKUP=PASS
LEXICAL_SHADOWING=PASS
UNARY_NEGATE=PASS
UNARY_INVERT=PASS
SUPPORTED_BINARY_OPERATORS=PASS
BINARY_PRECEDENCE=PASS
COMPARISON_LOWERING=PASS
NUMERIC_CASTS_USED_BY_STAGE1=PASS
LOCAL_INITIALIZATION=PASS
ASSIGNMENT_REASSIGNMENT=PASS
INSTRUCTION_RESULT_IDS=PASS
ORDERED_OPERAND_EDGES=PASS
SINGLE_RESULT_DEFINITION=PASS
UNSUPPORTED_MULTIPLY_DIVIDE_REMAINDER=FAIL_CLOSED/NOT_APPLICABLE
CANDIDATE_STAGE0_CHECK=PASS
FOCUSED_NATIVE_V2_CONFORMANCE=PASS_FOR_STAGE04_FIXTURES
S1_TYPED_VALUES=PASS
S2_DEF_USE=PASS
Z_MASK=3
```

`Z 3` is the expected completeness mask for a Stage04-only candidate. Do not promote to `Z 31`.

## Suggested local closure harness

Codex may create a temporary/local-only helper under `.artifacts/` that sequentially invokes the already-existing build/probe/conformance commands and writes a machine-readable summary. The helper must:

- consume the current generated candidate rather than regenerate semantics independently;
- never modify `selfhost/compiler/s3c_stage1.s3`;
- never mutate the control branch;
- stop on the first real failure;
- preserve stdout/stderr/exit code and artifact SHA256;
- be disposable and not required for final compiler correctness.

Do not spend a long cycle designing the helper. If creating it takes longer than executing the matrix manually, execute the matrix manually.

## Exit

If the Stage04 exit gate passes, re-fetch the control plane before Stage05. Automatic advance is allowed only if the live revision still permits it.
