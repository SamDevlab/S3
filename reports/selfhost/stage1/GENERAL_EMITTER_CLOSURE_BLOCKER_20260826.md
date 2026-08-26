# Stage1 General Emitter Closure Blocker

## Checkpoint

```text
PR=268
PR_STATE=OPEN
PR_DRAFT=YES
BRANCH=feature/actual-stage1-compiler-seed-20260824
HEAD=0ea67c4780f4b7577099690d2ef5cfc8dfe34529
CANONICAL_SOURCE_SHA256=20fddbb73eee9ae09de911493f2f2da01ab582c7a6de879ea2e557946716a341
CANONICAL_SOURCE_MUTATED=NO
```

## Native capacity candidate

The bounded candidate was exercised on the existing Linux x86-64 guest through
SSH. The final scratch candidate used for this checkpoint was:

```text
STAGE=06-full-fixed-v5
CANDIDATE_SHA256=d093733f5b57794a517d47c29b4622d334ef4198a7caaf49feb9595ba0771aaa
BUILD_RC=0
TRIVIAL_RUN_RC=0
TRIVIAL_STDERR_BYTES=0
```

The candidate includes measured call, argument, event, instruction, and block
capacity routing. Every physical array bank remains at 365 entries. The
three-bank active-call slot mapping and block-base offset writes were tested
after two native fail-closed diagnostics exposed their boundary errors.

## Self-emission result

The candidate was then run once against the complete canonical source. It did
not produce assembly and failed at the explicit emitter boundary:

```text
SELF_EMIT_EXIT=2
SELF_EMIT_ASSEMBLY_BYTES=0
SELF_EMIT_MARKER=S3_STAGE1_EMITTER_BLOCKED
SELF_EMIT_TRANSCRIPT=stage-probe/self-emit-stage06-v5-20260826T124641Z.raw.txt
AUDIT_VALUES=36 5 64 201 961 792 132 325 22 10 508 329 0 975 31 5 64 201 1072 3725 0 770 22 357 22 132
```

This is a real compiler capability blocker, not an SSH or guest failure. The
same guest successfully built and ran the candidate on the trivial fixture.

## Root cause

The verified Stage1 IR currently preserves bounded structural summaries and
some packed records, but it does not preserve enough information for a general
Assembly emitter. In particular, the current IR does not provide complete,
typed, independently addressable relationships for:

- parameter and local identity, type, mutability, and frame placement;
- value definitions, uses, and result destinations;
- arithmetic and comparison operand/result values;
- call result destinations and complete instruction ordering;
- foreign-call lowering and ABI argument/result shapes;
- branch conditions and complete per-block terminators;
- a canonical serialized IR artifact suitable for independent Stage2 input.

The existing emitter therefore supports only the verified literal-return
multi-function subset. Expanding it beyond that subset from aggregate counts or
event opcodes would invent compiler semantics, so the emitter remains
fail-closed with `S3_STAGE1_EMITTER_BLOCKED`.

## Typed IR scale oracle

The existing host compiler was used once as a measurement oracle for the same
canonical source. It was not used as a Stage1 backend or as self-hosting
evidence. Its verified typed IR contains:

```text
functions=36
parameters=68
registers=31012
memory_objects=510
blocks=2684
instructions=46573
instruction_results=30944
terminators=branch3:666,jump:1899,return:119
calls=internal:691,foreign:22
opcodes=add:162,branch3:666,call:713,compare:329,const:28244,
         convert:79,divide:14,jump:1899,load:1323,multiply:19,
         numeric_difference:61,return:119,store:12945
```

The Stage1 self-source audit at the same checkpoint reports only aggregate
event records and no semantic value definitions/results. The difference is
therefore an information-preservation gap. It cannot be closed by changing
capacity expectations, remapping event opcodes, or rereading the raw source in
the emitter.

The reproducible inventory is recorded in
`reports/selfhost/stage1/semantic-ir-requirements.json`. Its
`reference_typed_ir` section is explicitly labeled as a host-oracle
measurement and does not authorize Stage1, Stage2, or Stage3.

## Disposition

```text
SELF_EMIT=BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP
STAGE1_TO_STAGE2=BLOCKED_NOT_STARTED
STAGE2=NOT_CREATED
STAGE3=NOT_STARTED
T4=NOT_RUN_SOURCE_NOT_FROZEN

## Full-source parameter capacity recheck

The full-source parameter candidate was rebuilt after the bootstrap memory path
was corrected. The candidate source is the exact full-source transform, not the
earlier partial parameter probe:

```text
FULL_PARAMETER_CANDIDATE_SHA256=6c08d2f843c4c830f7f7c0cc38f6a22dc4e65ab2eb8166027e9d0a9e65b6d2d3
FULL_PARAMETER_CANDIDATE_BYTES=301828
FULL_PARAMETER_HOST_IO_CAPACITY=301828
FULL_PARAMETER_MAX_INSTRUCTIONS=1000000000
FULL_PARAMETER_BUILD=PASS
FULL_PARAMETER_TRIVIAL=PASS
FULL_PARAMETER_SELF_EXIT=2
FULL_PARAMETER_SELF_STDOUT_BYTES=0
FULL_PARAMETER_SELF_STDERR_BYTES=137
FULL_PARAMETER_SELF_MARKER=S3_STAGE1_EMITTER_BLOCKED
FULL_PARAMETER_SELF_STDERR_SHA256=eeec418143dd3f07e8e0780c3ace7a300c2aa78f1dfeb578ce98feef31ae29fc
FULL_PARAMETER_EXECUTABLE_SHA256=d11780cd30305da81045ee258f629b6fa0a2725bb1577cf912d95cac29d0c164
FULL_PARAMETER_ASSEMBLY_SHA256=3b1b2e1f6f38af86407fd391571f2aaf3ae8565aec41f7f4474fae19dd1eb72
FULL_PARAMETER_SELF_AUDIT=36 5 64 258 1504 1095 136 555 23 10 1439 555 0 1054 31 5 64 258 1093 4015 0 1091 4 588 23 136
FULL_PARAMETER_NATIVE_CAPACITY_BLOCKERS=CALLS_1414_GT_1095;BLOCK_HEADROOM_2;INSTRUCTION_RECORDS_4015_GT_1095
FULL_PARAMETER_RAW_TRANSCRIPT=parameter-ir-v2-native-full-capacity-20260826.raw.txt
```

The build and trivial execution prove only that the Stage0 boundary can
produce a candidate executable. The self-source still reaches the existing
fail-closed emitter gate, and the measured call/instruction pools remain
insufficient for a semantic general emitter.

## Write-only instruction-lane diagnostic

The three legacy `ir_instruction_records_*` banks were confirmed to be
write-only: each occurrence is either a declaration or a store, with no later
semantic read. A diagnostic candidate removed that lane while preserving the
event banks and event-derived instruction count. It was never applied to the
canonical source:

```text
DIAGNOSTIC_CANDIDATE_SHA256=40478686f3a6819290c1e1d6863879922476620aefd055850a93e7b4db1baf8a
DIAGNOSTIC_CANDIDATE_BYTES=280401
DIAGNOSTIC_BUILD=PASS
DIAGNOSTIC_TRIVIAL_EXIT=0
DIAGNOSTIC_TRIVIAL_STDOUT_BYTES=196
DIAGNOSTIC_TRIVIAL_STDERR_BYTES=0
DIAGNOSTIC_SELF_EXIT=2
DIAGNOSTIC_SELF_STDOUT_BYTES=0
DIAGNOSTIC_SELF_STDERR_BYTES=137
DIAGNOSTIC_SELF_MARKER=S3_STAGE1_EMITTER_BLOCKED
DIAGNOSTIC_SELF_AUDIT=36 5 64 232 1378 1095 136 523 22 10 1374 530 0 1041 31 5 64 232 1093 4015 0 1091 4 555 22 136
DIAGNOSTIC_SELF_STDERR_SHA256=24f06c037999263013ad44a30d50912217d543b678aecf3026fb47f98d75666f
DIAGNOSTIC_RAW_TRANSCRIPT=local-no-legacy-instruction-native-candidate-20260826.raw.txt
```

This diagnostic is rejected as a capability solution. Removing the stores
does not create instruction operands, results, ordering, or a verifier. The
next implementation must rewrite the event stream into the documented
ownerless IR-v2 instruction representation after a proven overwrite frontier;
until then the current fail-closed boundary remains mandatory.

```text
GENERAL_EMITTER=BLOCKED
SELF_EMIT=NOT_AUTHORIZED
STAGE1_TO_STAGE2=NOT_STARTED
STAGE3=NOT_STARTED
T4=NOT_RUN_SOURCE_NOT_FROZEN
CANONICAL_SOURCE_MUTATED=NO
```
```

## Parameter lane candidate checkpoint

The first bounded typed lane was exercised as a candidate only. It was built
from the canonical source through the existing discard-compaction transform and
the packed parameter metadata transform; the canonical source was not changed.
The transform initially exposed a host semantic error in its record-packing
expression. The transform was corrected to use typed local fields and a flat
`i64` packing expression, without adding a function signature. The focused
parameter-transform tests and host semantic analysis then passed.

The compact candidate was qualified through the Linux guest with the host I/O
path supplied explicitly:

```text
CANDIDATE_SOURCE_SHA256=dc76416843d5c131b5a1ffd4b91f6c94d705b4ea12977403ce74564c11586d1e
CANDIDATE_SOURCE_BYTES=175728
BUILD=PASS
TRIVIAL_RUN=PASS
TRIVIAL_STDOUT_BYTES=196
TRIVIAL_STDERR_BYTES=0
SELF_SOURCE_EXIT=2
SELF_SOURCE_STDOUT_BYTES=0
SELF_SOURCE_MARKER=S3_STAGE1_EMITTER_BLOCKED
AUDIT=34 5 64 23 75 656 107 94 6 4 155 92 0 699 29 5 64 23 329 1097 1213 653 3 104 6 107
```

This is bounded candidate evidence only. It shows the parameter lane can be
constructed and verified through the existing fail-closed emitter boundary; it
does not provide a general emitter, self-emission, Stage2, or promotion
evidence. The raw stderr transcript is preserved at
`parameter-ir-v2-native-candidate-20260826.raw.txt`.

The larger capacity candidate was not accepted: the guest kernel terminated
its Python build process for global OOM at approximately 6.7 GiB resident.
That result is recorded as host-capacity evidence, not as compiler semantics.

The subsequent bounded local-metadata candidate was also kept outside the
promotion path. Its host-side semantic audit passed through the parser and
semantic analyzer, and its static call-argument projection remained within the
existing pool, but its native qualification was terminated by the Linux guest
kernel before an output compiler or assembly artifact was produced:

```text
LOCAL_CANDIDATE_SOURCE_SHA256=dcf885aa93fef382e86c17fa10dbec13fb2b7f43e8bf75eb8dab4366004dce33
LOCAL_CANDIDATE_SOURCE_BYTES=193408
LOCAL_HOST_SEMANTIC_AUDIT=BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP
LOCAL_STATIC_CALL_ARGUMENT_AUDIT=PASS_STATIC_CALL_ARGUMENT_MODEL
LOCAL_NATIVE_BUILD=HOST_OOM
LOCAL_NATIVE_BUILD_OUTPUT=ABSENT
LOCAL_NATIVE_OOM_RSS_BYTES=6643076
LOCAL_NATIVE_OOM_TRANSCRIPT=guest-kernel-journal-20260826T142411Z
```

The kernel evidence identifies the killed process as the candidate's
`build_stage1_compiler.py`; no compiler diagnostic or partial executable was
accepted as native qualification. This is host-capacity evidence only. The
candidate still lacks the seven typed semantic lanes listed above, so it does
not authorize self-emission, Stage2, or a source promotion.

The focused host tests passed after the candidate fixes. No commit, push, PR
transition, benchmark, merge, or shutdown action was performed by this
checkpoint. The next valid work item is a lossless typed IR closure that keeps
the current fail-closed boundary until every required emitter relationship is
actually represented and verified.

The incremental validation results for this checkpoint are:

```text
LOCAL_FOCUSED_TESTS=23 passed, 1 skipped
VALUE_NAMESPACE_STATIC_AUDIT=PASS
CALL_ARGUMENT_STATIC_AUDIT=PASS
LOCAL_SEMANTIC_AUDIT=MISSING_7_LOSSLESS_TYPED_LANES
CANONICAL_SOURCE_MUTATED=NO
T4=NOT_RUN_SOURCE_NOT_FROZEN
```

## Reconciled semantic-storage audit

The host-side audit was rerun after adding explicit storage classification to
`tools/audit_stage1_semantic_ir_requirements.py`. It remains a diagnostic
oracle, not Stage1 evidence, and reports:

```text
STORAGE_AUDIT_STATUS=BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP
STORAGE_AUDIT_FUNCTIONS=31
STORAGE_AUDIT_CALLS=792
STORAGE_AUDIT_LOCALS=191
STORAGE_AUDIT_MISSING_TYPED_LANES=7
EVENT_RECORD_SCHEMA=packed(opcode, owner_function_plus_one, token_operand, token_offset)
EVENT_OPERAND_SOURCES=previous_value,value
EVENT_PACK_EXPRESSIONS=1
INSTRUCTION_COUNT_DERIVED_FROM_EVENT_COUNT=YES
LEGACY_INSTRUCTION_RECORD_READS=0
TYPED_VALUE_DEFINITIONS=NO
INSTRUCTION_OPERAND_VALUE_IDS=NO
INSTRUCTION_RESULT_VALUE_IDS=NO
CALL_ARGUMENT_VALUE_IDS=NO
CALL_RESULT_VALUE_IDS=NO
COMPLETE_TERMINATOR_VALUES=NO
CANONICAL_SERIALIZED_IR=NO
```

This closes an evidence gap in the audit only. It does not reinterpret the
aggregate event records as semantic instructions and does not authorize
general emission, self-emission, Stage2, or Stage3. The Linux guest remained
available over `s3-vm` (`Linux`, `x86_64`, Python `3.14.4`) with no active
compiler/test process during the check.

## Host IR capacity oracle

The same audit was run with its explicit host-IR oracle enabled. These values
describe the existing Python pipeline only; they are not Stage1 qualification
evidence:

```text
HOST_IR_FUNCTIONS=36
HOST_IR_PARAMETERS=68
HOST_IR_REGISTERS=31012
HOST_IR_MEMORY_OBJECTS=510
HOST_IR_BLOCKS=2684
HOST_IR_INSTRUCTIONS=46573
HOST_IR_INSTRUCTION_RESULTS=30944
HOST_IR_MAX_REGISTERS_PER_FUNCTION=28192
HOST_IR_MAX_BLOCKS_PER_FUNCTION=1913
HOST_IR_MAX_INSTRUCTIONS_PER_FUNCTION=42739
HOST_IR_TERMINATORS=branch3:666,jump:1899,return:119
HOST_IR_CALLS=internal:691,foreign:22
```

`main` is the dominant function in this oracle (`28,192` registers,
`1,913` blocks, `42,739` instructions). Therefore the earlier candidate
capacities of 730 or 1,095 blocks cannot be promoted by calibration. A valid
Stage1 design must either use an exact, bounded per-function/streaming
representation or prove an equivalent measured capacity; it may not silently
truncate or allocate an arbitrary matrix.

## Latest parameter-return IR checkpoint

The historical checkpoint sections above describe the source before the first
typed parameter-return lane. The current source checkpoint is:

COMMIT=cbdb963
CANONICAL_SOURCE_SHA256=9605cb6e757150460983f8304bf03d1fc9809c633b97c66aa4a15a7713168396
CANONICAL_SOURCE_BYTES=179657
CANONICAL_SOURCE_MUTATED=YES
PARAMETER_CAPACITY=68
PARAMETER_FIELDS=owner_function,name_identity,ordinal,declared_type
PARAMETER_MISSING_FIELDS=mutability,semantic_value_id

The general emitter now has one additional verified lowering form:
return <first-parameter> for a single valid parameter. The lowering uses the
SysV x86-64 rdi to rax move, so an i64 value is not truncated to 32 bits.
The gate rejects non-zero parameter ordinals, arities other than one, and
invalid parameter types.

Focused evidence for this source checkpoint:

HOST_FOCUSED_TESTS=3 passed, 1 skipped
HOST_SOURCE_PARSE=PASS
LINUX_NATIVE_BUILD=PASS
LINUX_NATIVE_IDENTITY_FIXTURE=PASS
LINUX_NATIVE_LITERAL_FIXTURE=PASS
NATIVE_IDENTITY_ASSEMBLY=mov rax, rdi
NATIVE_EXECUTABLE_SHA256=e43fb84a7938f9958804da9de87fccd285050be1b99b04c388f3f20d1e4743f7
NATIVE_ASSEMBLY_SHA256=15407b0bdd86761f58181b0973a26a7822bc5d91bcd58d588324c7968442716d

The same native artifact was run once on the current canonical source:

SELF_EMIT_EXIT=2
SELF_EMIT_ASSEMBLY_BYTES=0
SELF_EMIT_MARKER=S3_STAGE1_EMITTER_BLOCKED
SELF_EMIT_REASON=REMAINING_LOSSLESS_TYPED_IR_LANES
STAGE1_TO_STAGE2=BLOCKED_NOT_STARTED
STAGE2=NOT_CREATED
STAGE3=NOT_STARTED
T4=NOT_RUN_SOURCE_NOT_FROZEN

The parameter lane is therefore a qualified incremental capability, not a
Stage1 certification. The remaining blocker is still the absence of complete
typed local/value/instruction/call/terminator relationships and a canonical
serialized IR artifact for the other canonical functions. No Stage2 or Stage3
artifact was created.

## Latest selected-parameter IR checkpoint

The current implementation checkpoint is commit `3e3382d`. It extends the
previous parameter-return lane only through metadata already preserved by the
IR: a direct return may select parameter ordinals zero through five, mapped to
the integer SysV argument registers. The general-emitter gate also checks that
the function parameter range is representable and that every stored parameter
type is valid before emission.

```text
COMMIT=3e3382d
CANONICAL_SOURCE_SHA256=ec6bef92782fe253f4b1c1390d90f95017670a3cbb65497eff9dba12a2e7623c
CANONICAL_SOURCE_BYTES=185508
CANONICAL_SOURCE_MUTATED=YES
FUNCTIONS=32
NONFOREIGN_PARAMETERS=65
FOREIGN_PARAMETERS=4
PARAMETER_CAPACITY=68
PARAMETER_SUPPORTED_ORDINALS=0..5
PARAMETER_FIELDS=owner_function,name_identity,ordinal,declared_type
PARAMETER_MISSING_FIELDS=mutability,semantic_value_id
HOST_FOCUSED_TESTS=2 passed, 3 skipped
HOST_SOURCE_PARSE=PASS
LINUX_NATIVE_BUILD=PASS
LINUX_NATIVE_LITERAL_FIXTURE=PASS
LINUX_NATIVE_IDENTITY_FIXTURE=PASS
LINUX_NATIVE_SELECTED_PARAMETER_FIXTURE=PASS
NATIVE_SELECTED_PARAMETER_ASSEMBLY=mov rax, rdx
NATIVE_EXECUTABLE_SHA256=2dad907421cea2bdb159b29be71bdf15edd6c4fe566e60f36283408ce149ede7
NATIVE_ASSEMBLY_SHA256=78065c6c46ac93e036a2b3155ab58efb240c070bb88172c26a3e69d04ef4dae8
SELF_EMIT_EXIT=2
SELF_EMIT_ASSEMBLY_BYTES=0
SELF_EMIT_MARKER=S3_STAGE1_EMITTER_BLOCKED
SELF_EMIT_REASON=REMAINING_LOSSLESS_TYPED_IR_LANES
STAGE1_TO_STAGE2=BLOCKED_NOT_STARTED
STAGE2=NOT_CREATED
STAGE3=NOT_STARTED
T4=NOT_RUN_SOURCE_NOT_FROZEN
```

This remains an incremental capability proof, not Stage1 certification. The
canonical source still requires typed local/value definitions, instruction
operands and results, call value relationships, complete terminator values,
and a canonical serialized IR artifact. Consequently the fail-closed gate
still prevents self-emission, Stage2, and Stage3.
