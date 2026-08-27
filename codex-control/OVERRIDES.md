# Live overrides

CONTROL_REVISION: 8

No emergency stop is active.

Current direction:

- Stage 01 is complete.
- Stage 02 hosted contract qualification is recorded as PASS.
- Stage 03 transition was observed; detailed evidence remains backfill debt where not re-observed.
- Stage 04 remains the active implementation stage.
- Revision 8 activates **Codex + ChatGPT paired engineering mode** via `codex-control/PAIRING_MODE.md`.
- Revision 8 does not broaden Stage04 and does not authorize any later stage.
- `allow_automatic_stage_advance=false` for this closeout: do not enter Stage05 until the formal Stage04 checkpoint is jointly reviewed through the control plane.
- Finish any currently running atomic command before applying this revision. Do not duplicate an in-flight gate.
- Continue using `codex-control/STAGE04_FAST_PATH.md` and `codex-control/STAGE04_CONFORMANCE_EXPECTATIONS.md`.
- After a meaningful native matrix, strict conformance run, focused test gate, formal checkpoint, or before an implementation commit, emit the compact `PAIRING_CHECKPOINT` block defined in `PAIRING_MODE.md`.
- Fix one first real blocker per cycle. Do not make multiple speculative repairs from one failed run.
- Do not repeatedly re-check SSH, Linux/Python/cc, PR OPEN/DRAFT state, or already-proven function/block discovery unless a new execution failure implicates them.

PAIRED OWNERSHIP:

- Codex owns candidate implementation, local generator changes, Stage0 checks, Linux builds/runs, raw stdout/stderr/exit status, and exact candidate/binary identities.
- ChatGPT owns oracle/conformance interpretation, control-plane transitions, S3-Benchmarks triage/fixtures/evidence contracts, and narrowing the next semantic slice.
- Neither side may convert the other side's missing evidence into PASS.

STRICT STAGE04 CONFORMANCE NOTES:

- Candidate logical value IDs are allowed to differ from hosted IDs.
- Parameters are mapped by function/declaration order plus semantic metadata/source identity.
- Local bindings are mapped by function owner + exact source name/span + declared type + mutability.
- Local-binding `V` identity is distinct from an instruction-result `V`; do not collapse them because physical storage happens to coincide.
- Hosted instruction results are mapped through `R` edges.
- Ordered operand identity is checked through `O` edges.
- Numeric casts `to_i64`, `to_f64`, `to_tryte` lower as `CONVERT` opcode `10`, one operand, one result, `aux_a=-1`, `aux_b=-1`, one `O 0`, one `R 0`; target type belongs to the result `V` metadata. They are not call records.
- Immutable scalar initialization uses `MOVE` opcode `3` with one operand and one result.
- Mutable scalar initialization/reassignment uses `STORE` opcode `16`; scalar memory has length 1 and store operands are ordered `[index_value, stored_value]`. Initialization is not serialized as an extra S3IR2 field.

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
CONTROL_REVISION=8
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
NEXT_STAGE=05_CALLS_ARRAYS_S3 only after paired review updates the live control plane
```

When the Stage04 checkpoint is written, re-fetch control, emit a `PAIRING_CHECKPOINT` with `COMMAND_CLASS=CHECKPOINT`, and stop at the stage boundary. ChatGPT will evaluate it against the benchmark/oracle contracts and update the control plane if the exit evidence is sufficient.

If strict conformance fails, preserve one smallest representative mismatch and correct that semantic slice before broadening tests. Use `STAGE04_CONFORMANCE_EXPECTATIONS.md` to map verifier text to the owning candidate slice. A constant-fold-only difference must not be confused with a semantic mismatch; use parameter/local fixtures where needed to compare the preserved semantics.

If the control-branch fetch/read fails, Codex may finish the current atomic command but must not enter a new stage, create an implementation commit, mutate canonical Stage1 or cross a promotion/bootstrap gate until the live control revision can be read again.
