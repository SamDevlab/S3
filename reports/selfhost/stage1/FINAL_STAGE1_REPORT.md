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
x86-64. The same chain was then attempted in the isolated Linux guest; its
`/usr/bin/python3` does not provide `pytest`, so the chain stopped before the
native parameter build:

```text
WINDOWS_FULL_CHAIN=BLOCKED_HOST_REQUIRES_LINUX_X86_64
LINUX_GUEST_SSH=PASS
LINUX_GUEST_GUARD_TESTS=BLOCKED_PYTEST_UNAVAILABLE
LINUX_GUEST_BASE_CHAIN=NOT_RUN
COMPACTION_NATIVE=NOT_RUN
PARAMETER_IR_V2_NATIVE=NOT_RUN
LOCAL_IR_V2_NATIVE=NOT_RUN
GENERAL_EMITTER=BLOCKED_IR_V2_INCOMPLETE
SELF_EMIT=NOT_STARTED
STAGE1_TO_STAGE2=NOT_STARTED
STAGE2=NOT_CREATED
STAGE3=NOT_STARTED
```

This is an environment dependency blocker for the prepared chain, not a
call-model or compiler-semantics failure. The chain report preserves both
attempts in `codegen-ir-v2-full-candidate-chain.json`.

## Final disposition

```text
BLOCKER=1
PRIMARY_BLOCKER=LINUX_GUEST_PYTEST_UNAVAILABLE_FOR_PREPARED_IR_V2_CHAIN
NEXT=PROVIDE_PYTEST_IN_THE_EXISTING_LINUX_GUEST_THEN_RERUN_THE_PREPARED_CHAIN
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
