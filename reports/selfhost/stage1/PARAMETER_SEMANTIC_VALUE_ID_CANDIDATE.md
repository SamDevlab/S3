# Stage1 Parameter Semantic Value-ID Candidate

Date: 2026-08-26

```text
PR=268
BRANCH=feature/actual-stage1-compiler-seed-20260824
BASE_CANONICAL_SOURCE_SHA256=ec6bef92782fe253f4b1c1390d90f95017670a3cbb65497eff9dba12a2e7623c
BASE_CANONICAL_SOURCE_BYTES=185508
CANONICAL_SOURCE_MUTATED=NO
```

## Historical reconciliation

The earlier IR-v2 planning chain reserved a fixed 64-slot parameter value-ID
domain in a packed candidate. That candidate is historical and is no longer the
shape of the promoted canonical Stage1. The current source has four direct
68-slot parameter metadata lanes:

```text
ir_parameter_owner[68]
ir_parameter_name[68]
ir_parameter_ordinal[68]
ir_parameter_type[68]
```

The latest parameter checkpoint explicitly records `semantic_value_id` and
`mutability` as still missing fields. Reintroducing a separate packed 64-slot
lane would regress the promoted representation and recreate storage pressure.

## Candidate representation

The candidate instead defines the parameter metadata slot as the semantic value
identity:

```text
PARAMETER_VALUE_ID=PARAMETER_SLOT
PARAMETER_VALUE_NAMESPACE=[0,parameter_count)
EXTRA_VALUE_ID_STORAGE=0
```

For a `return <parameter>` instruction, `ir_return_kind == 2` continues to
distinguish the operand class, but `ir_return_operand` changes from the
function-local ABI ordinal to the global parameter slot. The emitter resolves
the semantic ID back to the ABI ordinal only when lowering:

```text
ir_parameter_ordinal[ir_return_operand[function]]
```

The general-emitter gate bounds the semantic ID by `parameter_count`, verifies
that the referenced parameter owner matches the function, and retains the
existing whole-parameter type-validation loop.

## Prepared proof

```text
PATCH_TOOL=tools/patch_stage1_parameter_semantic_value_ids.py
NATIVE_QUALIFIER=tools/qualify_stage1_parameter_semantic_value_ids.py
HOST_TEST=tests/test_stage1_parameter_semantic_value_ids.py
NATIVE_REPORT=reports/selfhost/stage1/parameter-semantic-value-native-candidate.json
```

The distinguishing native fixture intentionally creates multiple functions. In
the second function, parameter `z` has semantic value ID 4 but ABI ordinal 2.
A correct semantic-ID lowering must still emit:

```text
mov rax, rdx
```

Treating the semantic ID itself as the ABI ordinal would select the wrong
register, so the fixture is capable of detecting that class of regression.

## Current disposition

No Linux x86-64 execution has been observed for this candidate. GitHub Actions
for the PR is currently not providing runnable evidence; the latest observed
pre-candidate jobs failed before any step was executed. Therefore no native
PASS is claimed here.

```text
PARAMETER_SEMANTIC_VALUE_CANDIDATE=PREPARED_NOT_NATIVE_QUALIFIED
PARAMETER_SEMANTIC_VALUE_ID=REPRESENTED_IN_CANDIDATE
PARAMETER_MUTABILITY=STILL_NOT_REPRESENTED
LOCALS=NOT_REBASED_TO_PROMOTED_PARAMETER_NAMESPACE
UNIFIED_VALUE_DEF_USE=INCOMPLETE
GENERAL_EMITTER=INCREMENTAL_ONLY
SELF_EMIT=BLOCKED_REMAINING_LOSSLESS_TYPED_IR_LANES
STAGE1_TO_STAGE2=BLOCKED_NOT_STARTED
STAGE2=NOT_CREATED
STAGE3=NOT_STARTED
T4=NOT_RUN_SOURCE_NOT_FROZEN
FULL_SELF_HOSTING=NO
```

This candidate does not convert legacy structural value records into semantic
IR and does not authorize canonical promotion, Stage2 creation, or production
promotion.
