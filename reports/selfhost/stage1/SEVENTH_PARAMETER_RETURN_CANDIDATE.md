# Stage1 Seventh-Parameter Candidate Checkpoint

Date: 2026-08-26

```text
PR=268
BRANCH=feature/actual-stage1-compiler-seed-20260824
BASE_HEAD=0789ad2df5f200c6b35b67d591d10e016c1a557a
BASE_CANONICAL_SOURCE_SHA256=ec6bef92782fe253f4b1c1390d90f95017670a3cbb65497eff9dba12a2e7623c
CANONICAL_SOURCE_MUTATED=NO
```

## Why this is the next bounded step

The current verified emitter handles direct parameter returns for SysV x86-64
integer parameter ordinals 0 through 5 (`rdi`, `rsi`, `rdx`, `rcx`, `r8`,
`r9`). The latest native checkpoint explicitly leaves a seven-parameter
function fail-closed as unrepresentable.

Under the current leaf-function emission shape there is no prologue before the
parameter move. On SysV x86-64 the return address is therefore at `[rsp]` and
the seventh integer argument (ordinal 6) is the first stack-passed argument at
`[rsp+8]`.

The new candidate tooling performs only two semantic changes in a temporary
source:

1. raises the representability boundary from fewer than 7 parameters to fewer
   than 8 parameters;
2. lowers parameter ordinal 6 as `mov rax, qword ptr [rsp + 8]`.

The canonical `selfhost/compiler/s3c_stage1.s3` is not changed by this
checkpoint.

## Prepared evidence path

```text
PATCH_TOOL=tools/patch_stage1_seventh_parameter_return.py
NATIVE_QUALIFIER=tools/qualify_stage1_seventh_parameter_return.py
HOST_TEST=tests/test_stage1_seventh_parameter_return.py
NATIVE_REPORT=reports/selfhost/stage1/seventh-parameter-native-candidate.json
```

The Linux qualifier is required to prove all of the following before any
canonical promotion is considered:

```text
CANDIDATE_BUILD=PASS_REQUIRED
SEVENTH_PARAMETER_EMIT=PASS_REQUIRED
SEVENTH_PARAMETER_ASSEMBLY=mov rax, qword ptr [rsp + 8]
EIGHT_PARAMETER_BOUNDARY=S3_STAGE1_EMITTER_BLOCKED_REQUIRED
SELF_SOURCE_BOUNDARY=S3_STAGE1_EMITTER_BLOCKED_REQUIRED
CANONICAL_PROMOTION=SEPARATE_REVIEW_REQUIRED
```

## Certification disposition

```text
GENERAL_EMITTER=INCREMENTAL_ONLY
SEVENTH_PARAMETER_CANDIDATE=PREPARED_NOT_NATIVE_QUALIFIED
SELF_EMIT=BLOCKED_REMAINING_LOSSLESS_TYPED_IR_LANES
STAGE1_TO_STAGE2=BLOCKED_NOT_STARTED
STAGE2=NOT_CREATED
STAGE3=NOT_STARTED
T4=NOT_RUN_SOURCE_NOT_FROZEN
FULL_SELF_HOSTING=NO
```

This checkpoint does not reinterpret aggregate event records as semantic IR,
does not close local/value/call/terminator lanes, and does not authorize a
Stage2 artifact or production promotion.
