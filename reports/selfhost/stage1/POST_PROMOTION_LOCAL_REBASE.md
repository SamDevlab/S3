# Stage1 Post-Promotion Local IR Rebase

Date: 2026-08-26

```text
PR=268
BRANCH=feature/actual-stage1-compiler-seed-20260824
CANONICAL_SOURCE_SHA256=ec6bef92782fe253f4b1c1390d90f95017670a3cbb65497eff9dba12a2e7623c
CANONICAL_SOURCE_BYTES=185508
CANONICAL_SOURCE_MUTATED=NO
NATIVE_EVIDENCE=NO
```

## Why the historical local chain cannot be resumed unchanged

The original IR-v2 local candidate was prepared against a historical packed
parameter lane:

```text
ir_parameter_records: i64[64]
PARAMETER_VALUE_ID_DOMAIN=[0,64)
```

That is no longer the promoted Stage1 representation. The canonical compiler
now carries parameter metadata directly in four 68-slot lanes:

```text
ir_parameter_owner[68]
ir_parameter_name[68]
ir_parameter_ordinal[68]
ir_parameter_type[68]
```

The historical local transformer still explicitly requires
`ir_parameter_records: i64[64]`, and the historical value-namespace audit still
sets `PARAMETER_DOMAIN_END = 64`. They remain useful design evidence but are now
classified as `REBASE_REQUIRED_DO_NOT_CHAIN_AS_CANONICAL`.

## OOM evidence from the prior local candidate

The prior shape reached host-side semantic/static checks but the Linux build was
killed by host memory pressure before an executable or assembly artifact could
be accepted:

```text
PREVIOUS_LOCAL_CANDIDATE_SOURCE_BYTES=193408
PREVIOUS_LOCAL_HOST_SEMANTIC_AUDIT=BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP
PREVIOUS_LOCAL_STATIC_CALL_ARGUMENT_AUDIT=PASS_STATIC_CALL_ARGUMENT_MODEL
PREVIOUS_LOCAL_NATIVE_BUILD=HOST_OOM
PREVIOUS_LOCAL_NATIVE_BUILD_OUTPUT=ABSENT
```

That remains host-capacity evidence only, not proof of a compiler semantic
failure. The rebase therefore avoids copying the old large declaration state
machine into the current source.

## Rebased semantic namespace

The parameter semantic-value candidate prepared in this continuation makes the
parameter metadata slot itself the semantic Value ID. The local namespace must
follow that promoted shape dynamically:

```text
PARAMETER_VALUE_ID=parameter_slot
PARAMETER_VALUE_DOMAIN=[0,parameter_count)
LOCAL_VALUE_ID=parameter_count+global_local_record_slot
EXTRA_PARAMETER_VALUE_ID_STORAGE=0
EXTRA_LOCAL_VALUE_ID_STORAGE=0
```

This avoids a collision when the real parameter count exceeds the historical
64-slot reservation and avoids adding redundant Value-ID arrays.

## Compact local record

A local record needs to preserve semantic information rather than a premature
physical frame layout:

```text
FIELDS=owner_function,name_identity,declared_type,storage_kind,local_ordinal,fixed_extent
MUTABILITY=implicit_mut_declaration_for_current_local_grammar
STORAGE_KINDS=SCALAR,FIXED_ARRAY
PHYSICAL_FRAME_OFFSET=DEFERRED_TO_EMITTER
LOCAL_RECORD_CAPACITY_BOUND=365_NOT_PROMOTION_AUTHORITY
```

The semantic Value ID is derived from the global local record slot and is not a
packed field. The packed metadata boundary remains inside signed i64.

## Compact capture direction

The current scanner already preserves the immediately previous token. A rebased
candidate should extend that into a small bounded rolling history and recognize
only complete declaration suffixes:

```text
SCALAR_SUFFIX=mut name : type =
FIXED_ARRAY_SUFFIX=mut name : type [ extent ] =
MAXIMUM_ROLLING_HISTORY=7
```

This replaces the prior large local parser state machine with a bounded pattern
recognizer and is intended to reduce source growth before the next Linux native
build.

## New gate

```text
DESIGN_AUDIT=tools/audit_stage1_post_promotion_local_rebase.py
HOST_TEST=tests/test_stage1_post_promotion_local_rebase.py
GENERATED_REPORT=reports/selfhost/stage1/post-promotion-local-rebase-design-audit.json
EXPECTED_STATIC_STATUS=STATIC_POST_PROMOTION_LOCAL_REBASE_DESIGN_PASS
NEXT=IMPLEMENT_COMPACT_LOCAL_METADATA_CANDIDATE_WITH_DYNAMIC_PARAMETER_NAMESPACE
```

No static design result authorizes promotion. The future candidate must still be
built on Linux x86-64 through the real Stage0 boundary, must prove exact local
coverage for its own complete self-source, and must remain fail-closed on every
unsupported IR relationship.

## Certification disposition

```text
SEVENTH_PARAMETER_CANDIDATE=PREPARED_NOT_NATIVE_QUALIFIED
PARAMETER_SEMANTIC_VALUE_CANDIDATE=PREPARED_NOT_NATIVE_QUALIFIED
LOCAL_REBASE=DESIGN_GATE_PREPARED
LOCAL_NATIVE=NOT_RUN_REBASED_CANDIDATE_NOT_IMPLEMENTED
UNIFIED_VALUE_DEF_USE=INCOMPLETE
INSTRUCTION_IR=INCOMPLETE
CALL_LINKAGE=INCOMPLETE
TERMINATOR_LINKAGE=INCOMPLETE
GENERAL_EMITTER=INCREMENTAL_ONLY
SELF_EMIT=BLOCKED_REMAINING_LOSSLESS_TYPED_IR_LANES
STAGE1_TO_STAGE2=BLOCKED_NOT_STARTED
STAGE2=NOT_CREATED
STAGE3=NOT_STARTED
T4=NOT_RUN_SOURCE_NOT_FROZEN
FULL_SELF_HOSTING=NO
```
