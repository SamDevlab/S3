# Stage1 IR-v2 and General Emitter Qualification

## Current checkpoint

This is the current qualification state for PR #268. The campaign stopped at
the first real IR-v2 guard blocker. No source compiler change was made while
investigating it.

```text
PR=268
PR_STATE=OPEN
PR_DRAFT=YES
BRANCH=feature/actual-stage1-compiler-seed-20260824
BASE=integration/m271-m280-20260823
EFFECTIVE_START_HEAD=daf94959ad277804ff1d2de7852174ac7695b8f5
CANONICAL_SOURCE=selfhost/compiler/s3c_stage1.s3
CANONICAL_SOURCE_BYTES=166984
CANONICAL_SOURCE_SHA256=20fddbb73eee9ae09de911493f2f2da01ab582c7a6de879ea2e557946716a341
FINAL_TESTED_SOURCE_HEAD=081f3c53c42ad9562ae0770504b68c9de1947881
SOURCE_CHANGED_AFTER_LAST_NATIVE_GATES=NO
```

The source SHA and byte count match the native closure evidence. The source
last changed in `081f3c53c42ad9562ae0770504b68c9de1947881`; the current
working changes are qualification tooling and reports only.

## Environment and closed historical gate

```text
LINUX_NATIVE_ENVIRONMENT=PASS
LINUX_KERNEL=Linux Ubuntuserve 7.0.0-30-generic x86_64
LINUX_ARCH=x86_64
CALL_ARGUMENT_POOL_REQUIRED=736
CALL_ARGUMENT_POOL_CAPACITY=746
CALL_ARGUMENT_POOL_BANKS=[365,365,16]
CALL_ARGUMENT_POOL_HEADROOM=10
IR_CALL_ARGUMENT_POOL_CAPACITY=PASS_HISTORICAL_NATIVE_CLOSURE
```

The former pool-capacity blocker is closed and is not the current blocker.
The native closure measured `656` calls, `736` arguments, and maximum arity
`4` for the canonical source.

## Current IR-v2 guard result

The prepared full candidate chain was executed and failed closed at its guard
tests. The static audit is in
`codegen-ir-v2-call-argument-static-audit.json`; the chain transcript is in
`codegen-ir-v2-full-candidate-chain.json`.

```text
NATIVE_CURRENT_IDENTIFIER_OPEN_CANDIDATES=690
NATIVE_CURRENT_FUNCTION_SIGNATURES=34
NATIVE_CURRENT_CALLS=656
NATIVE_CURRENT_ARGUMENTS=736
NATIVE_CURRENT_MAX_ARITY=4

STATIC_CANONICAL_CALLS=792
STATIC_CANONICAL_ARGUMENTS=1041
STATIC_CANONICAL_MAX_ARITY=27
STATIC_CANONICAL_MAX_ACTIVE_CALL_DEPTH=2

CALL_ARGUMENT_MODEL=BLOCKED_CANONICAL_CALL_ARGUMENT_MODEL_DOES_NOT_MATCH_NATIVE_CLOSURE
```

The `690` native identifier-open candidates and `34` signatures were observed
with temporary instrumentation in an isolated copy only. The canonical source
was not modified. The static model is therefore not authorized for capacity
planning or candidate promotion. The two failing assertions are the intended
fail-closed equality guards, not a license to alter the expected native
numbers.

The qualification tooling was repaired only where it was objectively wrong on
Windows: subprocesses now use the active Python interpreter, and the parameter
transform uses a unique two-line anchor. These changes do not change compiler
source semantics.

## Capability status

```text
COMPACTION_NATIVE=NOT_NATIVE_QUALIFIED_CURRENT_CHAIN
PARAMETER_IR_V2_NATIVE=BLOCKED_NOT_RUN
LOCAL_IR_V2_NATIVE=BLOCKED_NOT_RUN
VALUE_NAMESPACE=NOT_STARTED
INSTRUCTION_IR_V2=NOT_STARTED
CALL_LINKAGE=NOT_STARTED
TERMINATOR_LINKAGE=NOT_STARTED
VERIFIER_V2=NOT_STARTED
SELF_IR=NOT_STARTED
SELF_VERIFY=NOT_STARTED
GENERAL_EMITTER=BLOCKED_IR_V2_INCOMPLETE
SELF_EMIT=NOT_STARTED
STAGE1_TO_STAGE2=NOT_STARTED
STAGE2=NOT_CREATED
STAGE3=NOT_STARTED
FULL_SELF_HOSTING=NO
```

No general emitter expansion, source rereading, source-specific hardcode,
Python code generation, embedded Stage2 assembly, or fake Stage2 was added.

## Validation

The current focused command was:

```text
python -m pytest -q tests/test_stage1_codegen_ir_v2_call_arguments.py tests/test_stage1_codegen_ir_v2_local_qualifier.py tests/test_stage1_codegen_ir_v2_full_chain.py tests/test_stage1_codegen_ir_v2_chain.py tests/test_stage1_codegen_ir_v2_parameters.py
```

```text
FOCUSED=27 passed, 2 failed
FOCUSED_FAILURES=the two canonical call-model equality guards
FULL_CHAIN_GUARD=2 failed, 15 passed
COMPILEALL=PASS
JSON_VALIDATION=PASS
DIFF_CHECK=PASS
```

The two focused failures are preserved as evidence of the blocker. They are
not reclassified as an infrastructure pass.

## T4 policy and historical evidence

No new T4 was run in this campaign. The historical T4 remains:

```text
T4_TESTED_HEAD=d8089a65fe43201e65dd6d0245a629d3c68eeae2
T4_SELECTED=455
T4_PASS=454
T4_FAIL=0
T4_TIMEOUT=1
T4_UNCLASSIFIED_TIMEOUT=0
T4_EXIT=1
T4_TIMEOUT_PATH=tests/test_stage1_compiler_seed.py
T4_TIMEOUT_CLASS=HEAVY_SELF_HOSTING
T4_APPLIED_TIMEOUT_SECONDS=180
T4_RUNS_THIS_CAMPAIGN=0
T4_REQUIRED_AFTER_FINAL_SOURCE_FREEZE=YES
TEST_LOGIC_CHANGED_AFTER_HISTORICAL_T4=YES
```

The preserved raw transcript is the pre-existing untracked artifact
`t4-final-20260825-010536.raw.txt`; it is intentionally not staged.

## Blocker and next step

```text
BLOCKER=1
PRIMARY_BLOCKER=BLOCKED_CANONICAL_CALL_ARGUMENT_MODEL_DOES_NOT_MATCH_NATIVE_CLOSURE
NEXT=RECONCILE_NATIVE_STAGE1_TOKEN_MODEL_WITH_STATIC_ORACLE
STAGE2_PRODUCER=NONE
```

The next unit must reconcile the native Stage1 token/event model with the
static oracle before any parameter, local, value, instruction, terminator,
verifier, general emitter, SELF_EMIT, or Stage2 claim can be made.

No merge, tag, release, benchmark, or Stage3 work was performed.
