# Stage1 Compact Local Metadata Candidate

Date: 2026-08-26

```text
PR=268
BRANCH=feature/actual-stage1-compiler-seed-20260824
CANONICAL_SOURCE_SHA256=ec6bef92782fe253f4b1c1390d90f95017670a3cbb65497eff9dba12a2e7623c
CANONICAL_SOURCE_BYTES=185508
CANONICAL_SOURCE_MUTATED=NO
NATIVE_QUALIFICATION=NOT_RUN
```

## Candidate chain

The candidate is intentionally built on the prepared parameter semantic-value
transform rather than the historical packed parameter IR-v2 transform:

```text
CANONICAL_STAGE1
  -> PARAMETER_VALUE_ID_IS_PARAMETER_SLOT
  -> COMPACT_LOCAL_METADATA
```

The seventh-parameter ABI candidate is kept independent so a local-metadata
failure cannot be confused with the separate stack-argument experiment.

## Local capture

The canonical scanner already maintains a 16-token ring. The compact candidate
uses that ring only when the current token is `=` and recognizes two complete
suffixes:

```text
SCALAR=mut name : type =
FIXED_ARRAY=mut name : type [ extent ] =
```

No historical local parser state machine is copied into the source. The
candidate stores one packed semantic record per recognized local:

```text
FIELDS=owner_function,name_identity,declared_type,storage_kind,local_ordinal,fixed_extent
STORAGE_KIND_1=SCALAR
STORAGE_KIND_2=FIXED_ARRAY
LOCAL_RECORD_CAPACITY_BOUND=365
PHYSICAL_FRAME_OFFSET=DEFERRED_TO_EMITTER
```

The current grammar's local declaration signal is `mut`, so mutability is
implicit in the record class. The semantic Value ID is also implicit:

```text
PARAMETER_VALUE_DOMAIN=[0,parameter_count)
LOCAL_VALUE_ID=parameter_count+global_local_record_slot
EXTRA_PARAMETER_VALUE_ID_ARRAY=NO
EXTRA_LOCAL_VALUE_ID_ARRAY=NO
```

## Fail-closed coverage rule

The canonical source already maintains both `local_count` and
`ir_local_record_count`. The candidate makes their relationship authoritative
for this bounded lane:

```text
REQUIRE=ir_local_record_count == local_count
REQUIRE=parameter_count + ir_local_record_count <= 1460
REQUIRE=every ir_local_records[0:ir_local_record_count] > 0
FAILURE=verifier_ok=0
```

Because the Stage1 scanner consumes the complete input source, this check also
covers all new `mut` declarations introduced by the candidate itself when the
candidate is run on its own self-source. A missed scalar/array declaration must
therefore stop before the expected general-emitter boundary.

## Prepared native qualification

```text
PATCH_TOOL=tools/patch_stage1_compact_local_metadata.py
NATIVE_QUALIFIER=tools/qualify_stage1_compact_local_metadata.py
HOST_TEST=tests/test_stage1_compact_local_metadata.py
NATIVE_REPORT=reports/selfhost/stage1/compact-local-native-candidate.json
```

The Linux x86-64 qualifier requires:

1. the parameter semantic-Value-ID regression fixture still emits `rsi` and
   `rdx` for the correct ABI ordinals;
2. a fixture containing one scalar local and one fixed-array local reaches
   `S3_STAGE1_EMITTER_BLOCKED` with native `local_count == 2` rather than a
   verifier/capacity failure;
3. the complete candidate self-source reaches the same explicit emitter
   boundary with a positive local count within the candidate bound.

The qualifier records the candidate source size and its delta against the prior
193408-byte local candidate so memory pressure can be compared factually rather
than assumed.

## Certification disposition

```text
COMPACT_LOCAL_CANDIDATE=PREPARED_NOT_NATIVE_QUALIFIED
SEVENTH_PARAMETER_CANDIDATE=PREPARED_NOT_NATIVE_QUALIFIED
PARAMETER_SEMANTIC_VALUE_CANDIDATE=PREPARED_NOT_NATIVE_QUALIFIED
LOCAL_METADATA=PREPARED_COMPACT_CANDIDATE
LOCAL_DEF_USE=NOT_STARTED
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

No canonical promotion is authorized by this preparation. Native Linux evidence
remains mandatory.
