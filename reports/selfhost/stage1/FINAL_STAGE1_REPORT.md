# Stage1 IR-v2 and General Emitter Qualification

## Checkpoint

```text
PR=268
PR_STATE=OPEN
PR_DRAFT=YES
BRANCH=feature/actual-stage1-compiler-seed-20260824
BASE=integration/m271-m280-20260823
EFFECTIVE_START_HEAD=c40ff38b80f6131c121fdd582674c605c0da305c
FINAL_TESTED_SOURCE_HEAD=c40ff38b80f6131c121fdd582674c605c0da305c
SOURCE_CHANGED_AFTER_FINAL_GATES=NO
CANONICAL_SOURCE_BYTES=166984
CANONICAL_SOURCE_SHA256=20fddbb73eee9ae09de911493f2f2da01ab582c7a6de879ea2e557946716a341
```

The canonical compiler source was not modified. The only source-side work in
this continuation was temporary instrumentation outside the repository. The
repository changes are the Stage1-equivalent oracle, focused regression tests,
and certification evidence.

## Native environment

```text
VIRTUALBOX_VM=Ubuntu server
VIRTUALBOX_VM_UUID=ed32ca05-d42e-4969-9de2-c331c86820a1
VIRTUALBOX_VM_INITIAL_STATE=poweroff
VIRTUALBOX_VM_FINAL_STATE=running
NAT_FORWARDING=127.0.0.1:2222->guest:22
LINUX_SSH=PASS
LINUX_NATIVE_ENVIRONMENT=PASS
LINUX_KERNEL=7.0.0-30-generic
LINUX_ARCH=x86_64
```

The existing VM and forwarding rule were reused. No additional VM, checkout,
reset, snapshot operation, or power operation was performed.

## Call-model differential

The native event trace and the corrected static trace agree exactly through
the native scan termination. The native counts are:

```text
NATIVE_IDENTIFIER_OPEN_CANDIDATES=690
NATIVE_FUNCTION_SIGNATURES=34
NATIVE_CALLS=656
NATIVE_CALL_ARGUMENTS=736
NATIVE_MAX_ARITY=4
NATIVE_MAX_ACTIVE_CALL_DEPTH=2
NATIVE_EVENT_COUNT=1392
NATIVE_LAST_EVENT_OFFSET=41376
```

The former static model continued after the native scanner reached the literal
`1000000000000` in `pack_ir_record` at offset `41502` (line `1304`, column
`21`). Stage1 packs tokens as:

```text
next_cursor * 1000000 + kind * 1000 + (value + 500)
```

That wide value carries into the decoded cursor lane. The static model was
corrected to perform the same pack/decode operation with truncation-toward-zero
division and to stop at the same decoded cursor boundary. No source hash,
offset subtraction, or canonical-count special case is used.

```text
STATIC_BEFORE_IDENTIFIER_OPEN_CANDIDATES=828
STATIC_BEFORE_FUNCTION_SIGNATURES=36
STATIC_BEFORE_CALLS=792
STATIC_BEFORE_CALL_ARGUMENTS=1041
STATIC_BEFORE_MAX_ARITY=27

STATIC_AFTER_IDENTIFIER_OPEN_CANDIDATES=690
STATIC_AFTER_FUNCTION_SIGNATURES=34
STATIC_AFTER_CALLS=656
STATIC_AFTER_CALL_ARGUMENTS=736
STATIC_AFTER_MAX_ARITY=4
STATIC_AFTER_MAX_ACTIVE_CALL_DEPTH=2

FIRST_CALL_DIVERGENCE_OFFSET=42725
FIRST_CALL_DIVERGENCE_LINE=1340
FIRST_CALL_DIVERGENCE_CONTEXT=s3_stage1_source_length()
FIRST_ARGUMENT_DIVERGENCE_OFFSET=81327
FIRST_ARGUMENT_DIVERGENCE_LINE=1477
FIRST_ARGUMENT_DIVERGENCE_CONTEXT=scan_token(cursor, length)
CALL_MODEL_NATIVE_STATIC_DIFFERENTIAL=PASS
CALL_ARGUMENT_MODEL=PASS_NATIVE_EQUIVALENT
CALL_ARGUMENT_POOL_REQUIRED=736
CALL_ARGUMENT_POOL_CAPACITY=746
CALL_ARGUMENT_POOL_HEADROOM=10
```

The divergence offsets are the first events the old full lexical model would
have emitted after native termination. They are evidence of the packed-token
lane overflow, not competing call classifications.

Evidence is recorded in:

```text
reports/selfhost/stage1/call-model-native-static-differential.json
reports/selfhost/stage1/codegen-ir-v2-call-argument-static-audit.json
```

## Validation

```text
CALL_MODEL_TESTS=PASS (17 passed)
IR_V2_FOCUSED_TESTS=PASS
WINDOWS_GUARD_TESTS=PASS
GUEST_PYTHON_VERSION=3.14.4
GUEST_VENV=/home/vboxuser/.cache/s3-pr268-venv
GUEST_PYTEST=PASS
GUEST_PYTEST_VERSION=9.1.1
PYTEST_INSTALL_SOURCE=GUEST_PIP_CACHE
GUEST_FOCUSED_SELECTED=130
GUEST_FOCUSED_PASSED=130
GUEST_FOCUSED_FAILED=0
GUEST_FOCUSED_SKIPPED=0
COMPILEALL=PASS
JSON_VALIDATION=PASS
DIFF_CHECK=PASS
T4_RUNS_THIS_CAMPAIGN=0
BENCHMARKS=NOT_RUN
```

The focused IR-v2 suite covered block capacity, call arguments, chain guards,
full-chain guards, local metadata, local qualification, locals, next-plan,
parameters, static preflight, storage reuse, and value namespace. The new
fixtures cover direct, nested, zero-argument, comma-separated, grouped,
array-index, identifier-argument, `discard`, `match`-compatible call shapes,
function signatures, foreign signatures, and three non-canonical mutation
shapes. The wide-literal fixture protects the native packed-token boundary.

## Prepared chain boundary

The prepared full chain was attempted in both available Python environments.
Windows guard tests passed, but the native base chain correctly requires Linux
x86-64. An isolated venv was then provisioned in the existing Linux guest and
the focused tooling suite passed. The native chain reached the compaction
candidate and stopped at its factual audit-invariant failure:

```text
WINDOWS_FULL_CHAIN=BLOCKED_HOST_REQUIRES_LINUX_X86_64
LINUX_GUEST_SSH=PASS
GUEST_PYTEST=PASS
GUEST_PYTEST_VERSION=9.1.1
GUEST_FOCUSED=130 passed, 0 failed, 0 skipped
LINUX_GUEST_GUARD_TESTS=PASS
LINUX_GUEST_BASE_CHAIN=BLOCKED_AT_CAPACITY_CANDIDATE
COMPACTION_NATIVE=FAIL_AUDIT_INVARIANTS
COMPACTION_CANDIDATE_BUILD=PASS
COMPACTION_TRIVIAL_COMPILE=PASS
COMPACTION_SELF_SOURCE_BOUNDARY=PASS
COMPACTION_ACTUAL_EVENTS=1097
COMPACTION_EVENT_HEADROOM=363
COMPACTION_ACTUAL_ASSIGNMENTS=75
COMPACTION_EXPECTED_ASSIGNMENTS=73
COMPACTION_ACTUAL_VALUES=1213
COMPACTION_EXPECTED_VALUES=1212
COMPACTION_ACTUAL_BLOCKS=329
COMPACTION_EXPECTED_BLOCKS=305
COMPACTION_FAILED_INVARIANTS=assignment_count_expected_delta,value_count_expected_delta,block_count_preserved
PARAMETER_IR_V2_NATIVE=NOT_RUN
LOCAL_IR_V2_NATIVE=NOT_RUN
GENERAL_EMITTER=BLOCKED_IR_V2_INCOMPLETE
SELF_EMIT=NOT_STARTED
STAGE1_TO_STAGE2=NOT_STARTED
STAGE2=NOT_CREATED
STAGE3=NOT_STARTED
```

The call-model gate remains closed and the canonical source remains unchanged.
The compaction candidate's event reduction is real, but it does not satisfy
the required structural deltas and block-count invariant, so parameter IR-v2
and local IR-v2 were correctly not attempted. The chain report and native
candidate report preserve the complete evidence.

## Final disposition

```text
BLOCKER=1
PRIMARY_BLOCKER=COMPACTION_NATIVE_FAILED_AUDIT_INVARIANTS
NEXT=FIX_COMPACTION_TRANSFORM_OR_ITS_EXACT_INVARIANTS_THEN_RERUN_THE_PREPARED_NATIVE_CHAIN
STAGE2=NOT_STARTED
STAGE3=NOT_STARTED
MERGE=NO
TAG=NO
RELEASE=NO
COMPUTER_SHUTDOWN_REQUESTED=NO
COMPUTER_RESTART_REQUESTED=NO
COMPUTER_LEFT_RUNNING=YES
```

No T4, benchmark, Stage3, merge, tag, release, or power action was performed.
