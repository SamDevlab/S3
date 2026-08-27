# Stage04 strict conformance expectations

Purpose: let Codex repair Stage04 against the strict S3IR2 v2 verifier directly instead of discovering semantic-shape mismatches only after broad native runs.

This file does not authorize canonical mutation, SELF_EMIT, Stage2, Stage3 or T4.

## Authority

Hosted semantic truth remains:

- `tools/stage1_semantic_ir_reference.py`
- `tools/stage1_semantic_stream_v2.py`
- `tools/verify_stage1_semantic_conformance_v2.py`

Candidate logical value IDs may differ from hosted IDs. Physical storage/scratch IDs are not semantic identity.

## S3IR2 opcode codes relevant to Stage04

```text
CONST=1
MOVE=3
INVERT=4
ADD=5
NUMERIC_DIFFERENCE=6
RELATE=9
CONVERT=10
COMPARE=13
LOAD=15
STORE=16
RETURN=23
```

Do not invent arithmetic MULTIPLY/DIVIDE/REMAINDER Stage04 support.

## I/O/R shape

Instruction encoding is:

```text
I instruction_id function_id block_id ordinal opcode result_count operand_count aux_a aux_b
```

For every instruction:

- ordered operands emit `O instruction_id operand_ordinal value_id`;
- every semantic instruction result emits exactly one `R` at its result ordinal;
- every `R` target must have a `V` row owned by the same function and with the correct semantic type/kind;
- scratch/storage numbers must never be substituted for logical value IDs.

`aux_a` is the memory-object ID when the hosted IR instruction has one; otherwise `-1`.
`aux_b` is an integer immediate when present; otherwise `-1`.

The strict verifier compares instruction ordinal, opcode, result count, operand count and scalar integer immediate (`aux_b`). It reconstructs semantic value identity independently.

## Numeric cast contract

Hosted numeric conversion lowers as one `CONVERT` instruction with one source operand and one result. No cast callee/call record is involved.

Expected candidate shape:

```text
I <id> <fn> <block> <ord> 10 1 1 -1 -1
O <id> 0 <source_value_id>
R <id> 0 <result_value_id>
```

The target cast type is carried by the result `V` type metadata, not by `aux_b`.

Therefore for `to_i64(x)`, `to_f64(x)` and `to_tryte(x)`:

- `CONVERT` opcode = 10;
- exactly one ordered `O 0` edge to the source value;
- exactly one `R 0` edge;
- result `V` kind = instruction result;
- result `V` type = target numeric type;
- no `C` or `A` record;
- valid Stage04 fixture remains `Z 3`;
- malformed/unsupported cast remains fail-closed (`Z 0`).

## Immutable local initialization

Hosted scalar immutable initialization normally allocates an IR result and emits `MOVE` from the initializer.

Expected semantic shape:

```text
MOVE opcode = 3
result_count = 1
operand_count = 1
O 0 -> initializer semantic value
R 0 -> MOVE result semantic value
```

Important: the source-level local binding `V kind=local_binding` and the instruction-result `V` for the `MOVE` are separate semantic values in the oracle. Do not collapse them merely because they may refer to the same physical storage in the candidate.

Local-binding identity is reconstructed by:

```text
mapped function owner
+ exact source identifier span/name
+ declared type
+ mutability
```

Instruction-result identity is reconstructed independently from the corresponding `R` edge.

## Mutable scalar initialization / reassignment

Hosted mutable scalar bindings use a mutable memory object of length 1. Initialization stores through a tryte index value `0` and the initializer value.

Representative initialization semantic shape:

```text
M <fn> <memory_id> <element_type> 1 1
CONST(index=0) -> semantic value
STORE opcode = 16
STORE operands in order: [index_value, stored_value]
result_count = 0
operand_count = 2
O 0 -> index value
O 1 -> stored value
```

Initialization is a property of the hosted IR instruction, but S3IR2 v2 does not serialize an independent initialization bit in the `I` record. Do not invent one in the frozen stream protocol.

Reassignment uses the same `STORE` operand ordering and memory semantics but is not a new local binding.

## Parameters

Parameter semantic values are mapped by:

- function order/identity;
- declaration order;
- type and mutability;
- exact source name span when available.

Do not require candidate parameter value IDs to equal hosted IDs.

## Strict verifier mismatch -> likely repair target

```text
function count/signature/source identity mismatch
  -> function/header discovery or source span

block count/owner/instruction-count mismatch
  -> statement/block discovery or instruction emission count

instruction semantic shape mismatch
  -> ordinal/opcode/result_count/operand_count/aux_b

parameter value count/type/mutability/source mismatch
  -> parameter V metadata / Pass1 binding

missing local binding
  -> local V(kind=local_binding), owner, source span, type or mutability

result edge count/ordinal mismatch
  -> missing/duplicate/wrong R edge

mapped value semantic metadata mismatch
  -> V owner/kind/type/mutability mismatch

missing mapped operand edge
  -> O edge missing, wrong ordinal, or wrong logical value

terminator value edge mismatch on simple return fixture
  -> T return_value_id not mapped to the same expression result
```

## Stage04 repair policy

On the first strict mismatch:

1. keep the exact source fixture, candidate stream and verifier JSON;
2. classify using the table above;
3. change only the smallest candidate-lowering slice that owns that mismatch;
4. rerun the smallest representative fixture;
5. then rerun the fixed regression matrix from `STAGE04_FAST_PATH.md`.

Do not redesign S3IR2 v2 to accommodate a candidate mismatch.

## Stage04 close condition

This document adds no new gate. It only makes the existing gate cheaper to satisfy.

Stage04 still closes only with representative strict conformance plus S1/S2 PASS and `Z 3` on valid Stage04 fixtures.