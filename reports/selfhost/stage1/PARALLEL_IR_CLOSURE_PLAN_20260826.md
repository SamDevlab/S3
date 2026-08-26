# PR #268 Parallel IR Closure Plan

Date: 2026-08-26

```text
BASE_HEAD=0789ad2df5f200c6b35b67d591d10e016c1a557a
PARALLEL_BRANCH=parallel/pr268-static-ir-closure-20260826
CANONICAL_COMPILER_CHANGED=NO
PR_268_HEAD_CHANGED_BY_THIS_BRANCH=NO
NATIVE_EVIDENCE_CREATED=NO
STAGE2_CREATED=NO
T4_RUNS=0
```

## Purpose

The active native scratch experiment is the compact block-capacity candidate.
It is intentionally not recreated or promoted on this branch. This branch only
contains work that can proceed without the Linux guest and without modifying
`selfhost/compiler/s3c_stage1.s3`.

The current scratch checkpoint reports 1,334 required structural blocks. Four
physical banks of 365 slots provide 1,460 slots, leaving 126 slots of bounded
headroom. The static contract freezes only bank routing and reversible record
encoding; the 1,334 measurement remains external native-checkpoint input and is
not promotion authority.

## A — compact block capacity contract

Prepared:

```text
tools/audit_stage1_compact_block_capacity.py
tests/test_stage1_compact_block_capacity_contract.py
```

The contract covers bank/slot boundaries, block 1333 -> bank 3 slot 238,
reversible `owner_function/terminator_kind/target_a/target_b` packing,
out-of-domain rejection and signed-i64 width.

```text
BLOCK_CAPACITY=1460
CHECKPOINT_REQUIRED_BLOCKS=1334
HEADROOM=126
MAX_PACKED_BLOCK_RECORD=415661999
SIGNED_I64_MAX=9223372036854775807
```

This is explicitly a **structural capacity** contract. It does not close W4:
complete `BRANCH3` semantics still need a condition Value ID and three target
edges, and `RETURN` needs a returned Value ID.

## B — checkpoint provenance

Prepared:

```text
tools/audit_stage1_checkpoint_consistency.py
tests/test_stage1_checkpoint_consistency.py
```

`FINAL_STAGE1_REPORT.md` and `FINAL_AUTONOMOUS_HANDOFF.txt` preserve older
campaign evidence and may legitimately reference older source hashes. The audit
therefore does not rewrite them. It establishes this read order instead:

```text
1. current canonical source hash/bytes
2. semantic-ir-requirements.json for that exact source
3. latest matching section in GENERAL_EMITTER_CLOSURE_BLOCKER_20260826.md
4. historical final reports/handoffs only for their campaign evidence
```

This prevents a historical checkpoint from being mistaken for current state.

## C — five parallel workstreams over seven missing lanes

Prepared:

```text
tools/audit_stage1_ir_closure_dependencies.py
tests/test_stage1_ir_closure_dependencies.py
```

The seven documented missing lanes remain intact, grouped into five workstreams:

```text
W1 symbol/value identity
   parameter identity/type/mutability/value ID
   local identity/type/mutability/storage/value ID
   typed constant definitions/interning

W2 instruction def/use/order
   operand Value IDs
   result Value IDs
   complete instruction ordering

W3 call dataflow/ABI
   call argument Value IDs
   call result destinations
   internal/foreign typed ABI shape

W4 terminator dataflow
   branch condition Value IDs
   complete jump/branch3/return semantics

W5 canonical Stage2 serialization
   deterministic independent IR artifact
```

Dependencies:

```text
W1 -> W2 -> W3
W1 + CURRENT_COMPACT_BLOCK_NATIVE_RESULT -> W4
W1 + W2 + W3 + W4 -> W5
```

## D — W1 value namespace rebase

Updated on this branch:

```text
reports/selfhost/stage1/codegen-ir-v2-value-namespace-contract.json
tools/audit_stage1_codegen_ir_v2_value_namespace.py
tests/test_stage1_codegen_ir_v2_value_namespace.py
```

The historical fixed reservation is removed:

```text
OLD_PARAMETER_DOMAIN=[0,64)
OLD_LOCAL_START=64

NEW_PARAMETER_CAPACITY_BOUND=68
NEW_PARAMETER_DOMAIN=[0,parameter_count)
NEW_LOCAL_START=parameter_count
NEW_LOCAL_ID=parameter_count+global_local_record_index
NEW_DYNAMIC_START=parameter_count+local_record_count
```

The physical capacity bound of 68 describes current direct parameter metadata;
it is not a fixed semantic-ID reservation.

The historical local transform is **not** silently patched. Instead a gate was
added:

```text
tools/audit_stage1_local_namespace_rebase.py
tests/test_stage1_local_namespace_rebase.py
EXPECTED_CURRENT_STATUS=LOCAL_TRANSFORM_REBASE_REQUIRED
```

It detects the existing `ir_parameter_records[64]` prerequisite and
`64 + local_capture_index` Value-ID encoding and refuses to classify that
transform as namespace-consistent. A future local transform must be rebuilt on
the current direct parameter metadata and then native-qualified.

## E — W2 instruction stream contract

Prepared:

```text
reports/selfhost/stage1/ir-v2-instruction-stream-contract.json
tools/audit_stage1_instruction_stream_contract.py
tests/test_stage1_instruction_stream_contract.py
```

The contract rejects arbitrary fixed instruction matrices. The existing host IR
is used only as a scale oracle; it is not Stage1 evidence. The logical record
requires:

```text
instruction_id
owner_block_id
ordinal_in_block
opcode
operand_value_ids
result_value_ids
type_or_signature_reference
immediate_or_aux_reference
```

Physical strategy:

```text
STREAMING_SERIALIZED_RECORDS
LEGACY_IR_INSTRUCTION_RECORDS_SEMANTIC_REUSE=NO
```

Legacy instruction stores remain non-semantic until an overwrite frontier and
new verifier prove exact count/order/def-use.

## F — W3 typed call linkage

Prepared:

```text
reports/selfhost/stage1/ir-v2-call-linkage-contract.json
```

Every semantic call must preserve:

```text
defining_instruction_id
callee_kind
callee identity
ordered argument_value_ids
result_value_ids
signature_reference
```

Foreign lowering derives ABI register/stack placement from the typed signature
and ordered semantic argument IDs, never lexical token position or arity alone.

## G — W4 complete terminators

Prepared:

```text
reports/selfhost/stage1/ir-v2-terminator-contract.json
```

Required semantic forms:

```text
RETURN  -> return_value_id
JUMP    -> one target_block_id
BRANCH3 -> condition_value_id + negative/zero/positive targets
```

The compact two-target block record remains `STRUCTURAL_CAPACITY_ONLY` and is
forbidden from claiming W4 closure.

Combined W3/W4 audit:

```text
tools/audit_stage1_call_terminator_contracts.py
tests/test_stage1_call_terminator_contracts.py
```

## H — W5 fail-closed Stage2 envelope

Prepared:

```text
reports/selfhost/stage1/stage2-serialized-ir-envelope-contract.json
tools/audit_stage2_serialized_ir_envelope.py
tests/test_stage2_serialized_ir_envelope.py
```

The design reserves magic `S3IR2`, schema version 1 and a four-bit completeness
mask:

```text
1 = W1 complete
2 = W2 complete
4 = W3 complete
8 = W4 complete
REQUIRED_MASK=15
```

Stage1 must not emit a Stage2-authoritative envelope unless the mask is 15.
Stage2 must reject any mask other than 15, count mismatches, duplicate/out-of-
order IDs or invalid cross-references. This is design only; Stage2 is not
created by this branch.

## I — one-command static parallel gate

Prepared:

```text
tools/audit_stage1_parallel_static_closure.py
```

It runs every audit above without invoking a native compiler, source transform,
Stage2 or T4.

Expected statuses include:

```text
STATIC_COMPACT_BLOCK_CAPACITY_CONTRACT_PASS
STATIC_PARALLEL_WORKSTREAM_MATRIX_PASS
CURRENT_CHECKPOINT_IDENTIFIED_HISTORICAL_HANDOFFS_PRESENT
  or CURRENT_CHECKPOINT_DOCUMENTS_CONSISTENT
STATIC_VALUE_NAMESPACE_DESIGN_PASS
LOCAL_TRANSFORM_REBASE_REQUIRED
  or LOCAL_TRANSFORM_NAMESPACE_CONSISTENT
STATIC_INSTRUCTION_STREAM_DESIGN_PASS
STATIC_CALL_TERMINATOR_DESIGN_PASS
STATIC_STAGE2_ENVELOPE_DESIGN_PASS_FAIL_CLOSED
```

Overall expected result:

```text
STATIC_PARALLEL_CLOSURE_PREPARED
NATIVE_ACTIONS_PERFORMED=0
STAGE2_CREATED=False
T4_RUNS=0
```

## What still must remain serialized

```text
CANONICAL_STAGE1_PROMOTION=WAIT_NATIVE_EVIDENCE
GENERAL_EMITTER_ENABLEMENT=WAIT_TYPED_RELATIONSHIPS
SELF_EMIT=WAIT_GENERAL_EMITTER
STAGE2_ARTIFACT=WAIT_COMPLETE_SERIALIZED_IR
STAGE3=WAIT_STAGE2
T4=WAIT_SOURCE_FREEZE
```

## Suggested execution when a repo runtime is available

```bash
python -m pytest -q \
  tests/test_stage1_compact_block_capacity_contract.py \
  tests/test_stage1_checkpoint_consistency.py \
  tests/test_stage1_ir_closure_dependencies.py \
  tests/test_stage1_codegen_ir_v2_value_namespace.py \
  tests/test_stage1_local_namespace_rebase.py \
  tests/test_stage1_instruction_stream_contract.py \
  tests/test_stage1_call_terminator_contracts.py \
  tests/test_stage2_serialized_ir_envelope.py

python -m tools.audit_stage1_parallel_static_closure
```

These are host/static gates only. They do not replace or duplicate the active
Linux native compact-block qualification.
