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

## Current continuation checkpoint

The worktree was resumed on the existing PR branch without discarding local
changes. The Linux guest remains reachable over SSH (`Linux 7.0.0-30-generic`,
`x86_64`, Python `3.14.4`, pytest `9.1.1`). The current worktree commit is
`0789ad2df5f200c6b35b67d591d10e016c1a557a`; the current compiler source in the
worktree hashes to
`e7d2a1cc694f6b1f5bec5149ee66c9df8ac804e5ad1fe519d3b8e015efe67dc1` and is
`205898` bytes. The worktree is intentionally dirty; unrelated existing
changes and the preserved historical T4 transcript were left untouched.

The heavy semantic audit completed with:

```text
STATUS=BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP
FUNCTIONS=32
CALLS=897
LOCALS=225
MISSING_LANES=6
```

The six missing lanes are parameter mutability/value identity, typed constant
definitions, instruction operands/results/order, call argument/result value
IDs, complete terminators, and a canonical serialized IR artifact. Explicit
parameter and local metadata lanes do not close those relationships. The
current native source probe still ends fail-closed at
`S3_STAGE1_EMITTER_BLOCKED` with exit code `2` and emits no assembly.

The required compaction 2x2 and event-level matrices were not claimed: the
existing packed-token native prerequisite remains unqualified, with the
authoritative earlier overflow evidence at source offset `41502`. This is
recorded in `compaction-native-2x2-differential.json`,
`compaction-event-differential.json`, and
`packed-token-lane-native-audit.json`. No matrix cell, event histogram,
semantic equivalence, full-source token coverage, Stage2 artifact, or Stage3
artifact is asserted.

```text
GENERAL_EMITTER=BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP
PARAMETER_IR_V2=NOT_AUTHORIZED
LOCAL_IR_V2=NOT_AUTHORIZED
SELF_EMIT=NOT_STARTED
STAGE2=NOT_STARTED
STAGE3=NOT_STARTED
T4=NOT_RUN
MERGE=NO
SHUTDOWN=NO
```

## Compaction native differential reconciliation (2026-08-27)

The authoritative historical compaction experiment was executed against the
exact canonical source S0 from commit `081f3c5`, without changing the dirty
canonical checkout. S0 is SHA-256
`20fddbb73eee9ae09de911493f2f2da01ab582c7a6de879ea2e557946716a341` and
`166984` bytes. S1 is the exact candidate that removes only
`ir_ast_event_opcode = 5` and `ir_ast_event_operand = value`: SHA-256
`cfc65f801cfa7fa7e417c144c866f3db38acc2a0630e1ba30be12ac13f4383f9`,
`166883` bytes, a `-101` byte delta.

The native E0/E1 x S0/S1 matrix built both executables successfully and all
four cells reached the deliberate `S3_STAGE1_EMITTER_BLOCKED` boundary with
exit `2` and empty assembly output. E0 observed `305` blocks and `1460`
retained events; E1 observed `329` blocks and `1097` retained events. All AST
fields, calls, values, and non-discard event histogram lanes were unchanged.
Temporary native histogram instrumentation showed `1796` attempted E0 events,
including `699` opcode-5 events, versus `1097` E1 events with zero opcode-5
events. No other opcode differed.

The old assignment/value expectations were invalid native gates. The source
delta is genuinely `-2` assignment-observation tokens and `-1` numeric token,
but the legacy packed-token cursor becomes invalid at offset `41502` on
`1000000000000`, while the removed assignments are at offsets `88492` and
`88540`. They are therefore outside the native observable prefix. The block
delta is capacity truncation: E0 retains the first `1460` of `1796` events,
whereas E1 retains all `1097` non-discard events and consequently reaches later
control events. It is not evidence that compaction creates CFG blocks.

Five native synthetic fixtures independently confirmed that the transform
removes only the redundant discard aggregate event and preserves call,
assignment, control, return, and block-driving behavior. The static prefix
oracle agrees with the native histogram after filtering opcode 5.

```text
COMPACTION_TRANSFORM=VALID_NARROW_DISCARD_EVENT_COMPACTION
OLD_AUDIT_INVARIANTS=INVALID_TEXTUAL_DELTAS_AND_TRUNCATED_BLOCK_COMPARISON
COMPACTION_NATIVE_MATRIX=EXECUTED
COMPACTION_SEMANTIC_EQUIVALENCE=PASS_OBSERVED_PREFIX_AND_SYNTHETIC_FIXTURES
COMPACTION_NATIVE_PROMOTION=BLOCKED_PACKED_TOKEN_VALUE_LANE_FULL_SOURCE_COVERAGE
BLOCK_DRIFT_CAUSE=EVENT_POOL_TRUNCATION_AFTER_DISCARD_COMPACTION_WITH_PACKED_TOKEN_FRONTIER
PACKED_TOKEN_FIRST_INVALID_OFFSET=41502
DISCARD_REMOVED_OPCODE_OFFSET=88492
DISCARD_REMOVED_OPERAND_OFFSET=88540
PACKED_TOKEN_LANE=DEEPEST_REMAINING_BLOCKER
GENERAL_EMITTER=BLOCKED_IR_V2_INCOMPLETE
SELF_EMIT=NOT_STARTED
STAGE2=NOT_STARTED
STAGE3=NOT_STARTED
T4=NOT_RUN
MERGE=NO
SHUTDOWN=NO
```

## Latest capacity reconciliation

The current external candidate `scratch-packed-block-capacity-current.s3` was
generated from canonical source SHA256
`c632680332fc6a0e83352db1051aec109887d3b67724ae41a6311d21faf5dac8` and has
SHA256 `52c8d449a495cfe8d9d3a77aa50363c1ecd56fb467af4392cbfa577992c04eed`
and 266025 bytes. It uses four bounded 365-entry packed block banks, for a
capacity of 1460 blocks, with owner, terminator, and two CFG targets encoded in
one reversible `i64` record. The canonical source was not changed.

The candidate built natively on Linux x86-64 with the standard host I/O
(`BUILD_EXIT=0`, 802 seconds) and with a temporary 300000-byte host-I/O copy
(`BUILD_EXIT=0`, 855 seconds). The standard input window is 262144 bytes, so
the candidate's own source cannot be treated as a standard-window
self-emission input. Under the temporary window, the candidate self-probe
failed closed at the fixed 100000000-instruction limit in `identifier_hash`;
it produced no assembly. This candidate is therefore not promoted.

The same candidate binary processed the 209333-byte canonical source and
reached the deliberate emitter boundary with exit 2 and audit:

```text
S3_STAGE1_AUDIT 37 5 70 246 1278 899 133 413 31 10 610 420 0 1140 32 5 70 228 1364 4514 0 877 22 454 31 133
S3_STAGE1_EMITTER_BLOCKED
```

The focused IR-v2/capacity/emitter tests remain green at `74 passed, 3
skipped`; the skips are the local Linux-native tests and do not authorize
self-emission. The general emitter remains blocked because the existing IR
does not preserve typed constants, instruction operand/result/order relations,
call argument/result value IDs, complete terminator values, or a canonical
serialized IR artifact. SELF_EMIT, Stage2, Stage3, and T4 remain unstarted.

```text
PACKED_BLOCK_CAPACITY_CANDIDATE=NOT_PROMOTED
GENERAL_EMITTER=BLOCKED_IR_V2_INCOMPLETE
SELF_EMIT=NOT_AUTHORIZED
STAGE1_TO_STAGE2=NOT_STARTED
STAGE2=NOT_CREATED
STAGE3=NOT_STARTED
T4=NOT_RUN_SOURCE_NOT_FROZEN
MERGE=NO
```

## Latest checkpoint reconciliation

The current PR #268 worktree remains intentionally uncommitted and on
`feature/actual-stage1-compiler-seed-20260824` at
`0789ad2df5f200c6b35b67d591d10e016c1a557a`. The canonical source currently
hashes to
`c632680332fc6a0e83352db1051aec109887d3b67724ae41a6311d21faf5dac8` and is
`209333` bytes. The repaired token lane builds natively on the Linux guest,
and its full-source probe reaches the fail-closed emitter boundary with
`S3_STAGE1_EMITTER_BLOCKED`, exit `2`, and no assembly output.

The static full-source model requires `899` calls, `1165` call arguments,
maximum arity `27`, `4456` pre-compaction events, and `1334` compacted blocks.
The widened capacity candidate was generated at `497304` bytes, but local
qualification was stopped under host memory pressure before a semantic or
native result could be accepted. It was not promoted and did not mutate the
canonical source.

The focused checkpoint gates now pass with `74 passed, 3 skipped`, and
`compileall` passes. The general emitter remains blocked by five lossless
typed IR lanes: typed constant definitions, instruction operand/result/order
relations, call argument/result value IDs, complete terminator values, and a
canonical serialized IR artifact. SELF_EMIT, Stage2, Stage3, and T4 remain
unstarted or not run; no merge or publication action is authorized.

```text
CAPACITY_CANDIDATE=NOT_ACCEPTED_HOST_MEMORY_PRESSURE
GENERAL_EMITTER=BLOCKED_IR_V2_INCOMPLETE
SELF_EMIT=NOT_AUTHORIZED
STAGE1_TO_STAGE2=NOT_STARTED
STAGE2=NOT_CREATED
STAGE3=NOT_STARTED
T4=NOT_RUN_SOURCE_NOT_FROZEN
MERGE=NO
```

## Incremental capacity evidence

The isolated call/argument candidate was natively built and crossed the old
call boundary: `935` calls were observed before the fail-closed emitter
marker, with `323` blocks and `1460` events/instructions still limited by the
unexpanded lanes. The candidate source was
`34736b1cf78528edae5b5eed80cc273324c665c5674755c66ca784012619b298`, and its
executable was
`bf1adeba6322d54c8b35cb533185c9397ce9fd51702905a02d2af0977200795d`.

The event-only candidate built successfully but reached the instruction limit
because block storage remained at `365`. The combined event/instruction
candidate was rejected by the Assembly verifier because its frame required
`141693` logical trits versus the `131072` limit. No capacity candidate was
promoted. The valid next design must compact or reuse block representation
within the existing frame budget; it must not silently truncate control flow.

```text
CALL_CAPACITY_TRIAL=PASS_NATIVE_BUILD_AND_BOUNDARY_PROBE
EVENT_CAPACITY_TRIAL=BUILD_PASS_BLOCK_CAPACITY_BLOCKER
EVENT_INSTRUCTION_TRIAL=FRAME_MEMORY_REJECTED
CAPACITY_CANDIDATE_PROMOTED=NO
GENERAL_EMITTER=BLOCKED_IR_V2_INCOMPLETE
SELF_EMIT=NOT_AUTHORIZED
STAGE2=NOT_STARTED
STAGE3=NOT_STARTED
T4=NOT_RUN_SOURCE_NOT_FROZEN
```

## Authoritative current-state reconciliation (2026-08-26)

The historical checkpoint values earlier in this report are retained for
lineage. The following block is the authoritative state of the current PR
#268 worktree.

```text
AUTHORITATIVE_WORKTREE_HEAD=0789ad2df5f200c6b35b67d591d10e016c1a557a
AUTHORITATIVE_CANONICAL_SOURCE_SHA256=c632680332fc6a0e83352db1051aec109887d3b67724ae41a6311d21faf5dac8
AUTHORITATIVE_CANONICAL_SOURCE_BYTES=209333
AUTHORITATIVE_TOKEN_LANE_NATIVE_BUILD=PASS
AUTHORITATIVE_TOKEN_LANE_NATIVE_PROBE=REACHED_FULL_SOURCE_AUDIT
AUTHORITATIVE_TOKEN_LANE_NATIVE_PROBE_MARKER=S3_STAGE1_EMITTER_BLOCKED
AUTHORITATIVE_TOKEN_LANE_NATIVE_PROBE_EXIT=2
AUTHORITATIVE_FULL_SOURCE_CALLS=899
AUTHORITATIVE_FULL_SOURCE_CALL_ARGUMENTS=1165
AUTHORITATIVE_FULL_SOURCE_MAX_ARITY=27
AUTHORITATIVE_EVENTS_BEFORE_COMPACTION=4456
AUTHORITATIVE_EVENTS_AFTER_COMPACTION=3329
AUTHORITATIVE_BLOCKS_AFTER_COMPACTION=1334
AUTHORITATIVE_SEMANTIC_AUDIT=BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP
AUTHORITATIVE_MISSING_LOSSLESS_TYPED_LANES=5
AUTHORITATIVE_FOCUSED_TESTS=74 passed, 3 skipped
AUTHORITATIVE_COMPILEALL=PASS
AUTHORITATIVE_GENERAL_EMITTER=BLOCKED_IR_V2_INCOMPLETE
AUTHORITATIVE_SELF_EMIT=NOT_AUTHORIZED
AUTHORITATIVE_STAGE2=NOT_STARTED
AUTHORITATIVE_STAGE3=NOT_STARTED
AUTHORITATIVE_T4=NOT_RUN_SOURCE_NOT_FROZEN
AUTHORITATIVE_MERGE=NO
```

## Current continuation checkpoint after parameter metadata closure

The current worktree source was re-audited after adding explicit parameter
mutability and semantic value-id lanes. The source identity and semantic audit
are now:

```text
PR=268
PR_STATE=OPEN
PR_DRAFT=YES
BRANCH=feature/actual-stage1-compiler-seed-20260824
WORKTREE_HEAD=0789ad2df5f200c6b35b67d591d10e016c1a557a
CURRENT_SOURCE_SHA256=03ffebbf1512da6400c9612dbab778a06f9125641185d10995c045d1556799c5
CURRENT_SOURCE_BYTES=208723
STATUS=BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP
FUNCTIONS=32
CALLS=898
LOCALS=228
MISSING_LOSSLESS_TYPED_LANES=5
PARAMETER_METADATA=PRESERVED_WITH_FAIL_CLOSED_VERIFIER
```

The five remaining lossless lanes are typed constant definitions, instruction
operands/results/order, call argument/result value ids, complete terminators,
and a canonical serialized IR artifact. The explicit parameter lane is bounded
at 70 entries and verifies owner, name, type, mutability, and semantic value id.
No aggregate event or lexical record is promoted to a typed semantic relation.

```text
COMPACTION_2X2=NOT_RUN_PREREQUISITE_TOKEN_LANE_NATIVE_FAIL
EVENT_DIFFERENTIAL=NOT_RUN_PREREQUISITE_TOKEN_LANE_NATIVE_FAIL
PACKED_TOKEN_LANE=NATIVE_REQUALIFICATION_REQUIRED
GENERAL_EMITTER=BLOCKED_IR_V2_INCOMPLETE
SELF_EMIT=NOT_STARTED
STAGE1_TO_STAGE2=NOT_STARTED
STAGE2=NOT_CREATED
STAGE3=NOT_STARTED
T4=NOT_RUN
MERGE=NO
SHUTDOWN=NO
```

## Final local reconciliation after packed-block tool recovery

The packed-block candidate generator was restored to its valid four-bank
layout. Regeneration from the canonical source reproduced the previously
qualified candidate exactly, with SHA256
`52c8d449a495cfe8d9d3a77aa50363c1ecd56fb467af4392cbfa577992c04eed` and
`266025` bytes. The candidate contains four physical `365`-entry banks and a
total block capacity of `1460`; the canonical source remains unchanged.

The intermediate single-vector experiment was rejected by the Assembly array
limit: an `i64[1460]` declaration is invalid because the maximum array length
is `365`. It is not evidence for promotion and was not used in any native
claim.

```text
PACKED_BLOCK_GENERATOR=RESTORED_FOUR_BANK_LAYOUT
PACKED_BLOCK_CANDIDATE=52c8d449a495cfe8d9d3a77aa50363c1ecd56fb467af4392cbfa577992c04eed
PACKED_BLOCK_CANDIDATE_BYTES=266025
PACKED_BLOCK_CAPACITY=1460
SINGLE_VECTOR_VARIANT=REJECTED_ARRAY_LENGTH_LIMIT
SINGLE_VECTOR_ARRAY_LENGTH=1460
SINGLE_VECTOR_ARRAY_LIMIT=365
CANONICAL_SOURCE_MUTATED=NO
GENERAL_EMITTER=BLOCKED_IR_V2_INCOMPLETE
SELF_EMIT=NOT_AUTHORIZED
STAGE2=NOT_CREATED
STAGE3=NOT_STARTED
T4=NOT_RUN_SOURCE_NOT_FROZEN
MERGE=NO
```

## Final authoritative compaction state (2026-08-27)

The exact native E0/E1 x S0/S1 matrix is recorded in
`compaction-native-2x2-differential.json` and
`compaction-event-differential.json`. The four cells built successfully and
reached the expected fail-closed emitter boundary with exit `2` and empty
output. The historical canonical S0 was not modified.

```text
COMPACTION_TRANSFORM=VALID_NARROW_DISCARD_EVENT_COMPACTION
OLD_AUDIT_INVARIANTS=INVALID_TEXTUAL_DELTAS_AND_TRUNCATED_BLOCK_COMPARISON
TEXTUAL_ASSIGNMENT_DELTA=-2
TEXTUAL_NUMERIC_DELTA=-1
NATIVE_OBSERVED_ASSIGNMENT_DELTA=0
NATIVE_OBSERVED_VALUE_DELTA=0
E0_ATTEMPTED_EVENTS=1796
E0_RETAINED_EVENTS=1460
E0_DISCARD_EVENTS=699
E0_BLOCKS=305
E1_RETAINED_EVENTS=1097
E1_DISCARD_EVENTS=0
E1_BLOCKS=329
NON_DISCARD_EVENT_HISTOGRAM=IDENTICAL
COMPACTION_SEMANTIC_EQUIVALENCE=PASS_OBSERVED_PREFIX_AND_SYNTHETIC_FIXTURES
BLOCK_DRIFT_CAUSE=EVENT_POOL_TRUNCATION_AFTER_DISCARD_COMPACTION_WITH_PACKED_TOKEN_FRONTIER
PACKED_TOKEN_FIRST_INVALID_OFFSET=41502
DISCARD_OPCODE_ASSIGNMENT_OFFSET=88492
DISCARD_OPERAND_ASSIGNMENT_OFFSET=88540
COMPACTION_NATIVE_PROMOTION=BLOCKED_PACKED_TOKEN_VALUE_LANE_FULL_SOURCE_COVERAGE
GENERAL_EMITTER=BLOCKED_IR_V2_INCOMPLETE
SELF_EMIT=NOT_STARTED
STAGE2=NOT_STARTED
STAGE3=NOT_STARTED
T4=NOT_RUN
MERGE=NO
SHUTDOWN=NO
```

The required terminal fields for this campaign are:

```text
PR_STATE=OPEN
PR_DRAFT=YES
BRANCH=feature/actual-stage1-compiler-seed-20260824
EFFECTIVE_START_HEAD=326d42f8a2623ced5a2151d6daaf2d67743faca8
FINAL_HEAD=6e6b837e295ba79bd456e2fc96de9f8ff7ea2a15
LINUX_NATIVE_ENVIRONMENT=PASS
GUEST_PYTEST=PASS_PYTEST_9.1.1
CANONICAL_SOURCE_SHA256=739dc6ac16c2c79a4f3bff0b7ca2f40324171b3ad155f7a6265747d441cb5758
CANONICAL_SOURCE_BYTES=211674
DISCARD_TRANSFORM_START_OFFSET=88492
PACKED_TOKEN_OVERFLOW_OFFSET=41502
E0_S0_EVENTS=1460_RETAINED_1796_ATTEMPTED
E0_S0_ASSIGNMENTS=75
E0_S0_VALUES=1213
E0_S0_BLOCKS=305
E0_S1_EVENTS=1460_RETAINED_1796_ATTEMPTED
E0_S1_ASSIGNMENTS=75
E0_S1_VALUES=1213
E0_S1_BLOCKS=305
E1_S0_EVENTS=1097
E1_S0_ASSIGNMENTS=75
E1_S0_VALUES=1213
E1_S0_BLOCKS=329
E1_S1_EVENTS=1097
E1_S1_ASSIGNMENTS=75
E1_S1_VALUES=1213
E1_S1_BLOCKS=329
INPUT_SOURCE_EFFECT=NONE_OBSERVABLE
COMPILER_BEHAVIOR_EFFECT=ONLY_OPCODE_5_DISCARD_AGGREGATE_REMOVED
SELF_COUPLING_EFFECT=NONE_OBSERVABLE
BLOCK_DRIFT_CAUSE=EVENT_POOL_TRUNCATION_AFTER_DISCARD_COMPACTION_WITH_PACKED_TOKEN_FRONTIER
TOKEN_SOURCE_COVERAGE=INCOMPLETE_LEGACY_41502_OF_166984_STATIC_REPAIR_100_PERCENT_MODEL_ONLY
PACKED_TOKEN_FRONTIER_STABLE=NO_LEGACY_REPAIR_NOT_NATIVE_PROMOTED
BASELINE_EVENT_COUNT=1796_ATTEMPTED_1460_RETAINED
CANDIDATE_EVENT_COUNT=1097
DISCARD_EVENTS_REMOVED=699
NON_DISCARD_EVENT_DIFFERENTIAL=NONE
CALL_SEQUENCE_PRESERVED=PASS_NATIVE_COUNTERS_AND_STATIC_PREFIX
STORE_SEQUENCE_PRESERVED=PASS_STATIC_EVENT_MODEL_NO_STORE_REMOVED
CONTROL_SEQUENCE_PRESERVED=PASS_NATIVE_HISTOGRAM_AND_STATIC_PREFIX
RETURN_SEQUENCE_PRESERVED=PASS_NATIVE_HISTOGRAM_AND_STATIC_PREFIX
COMPACTION_ROOT_CAUSE=COMPACTION_VALID_OLD_INVARIANTS_INVALID_PACKED_TOKEN_LANE_BLOCKS_FULL_SOURCE
COMPACTION_SEMANTIC_EQUIVALENCE=PASS_OBSERVED_PREFIX_AND_SYNTHETIC_FIXTURES
COMPACTION_NATIVE=BLOCKED_PACKED_TOKEN_VALUE_LANE_FULL_SOURCE_COVERAGE
TOKEN_LANE_FIX_REQUIRED=YES
TOKEN_LANE_STATUS=LEGACY_PACKED_VALUE_OVERFLOW_STATIC_REPAIR_ONLY
FULL_CHAIN_STATUS=BLOCKED_BEFORE_PARAMETER_LOCAL_RESUME
PARAMETER_IR_V2_NATIVE=NOT_RESUMED_BLOCKED_BY_FULL_SOURCE_QUALIFICATION
LOCAL_IR_V2_STATIC_PREFLIGHT=DEFERRED
LOCAL_IR_V2_NATIVE=DEFERRED
VALUE_NAMESPACE=NOT_STARTED
GENERAL_EMITTER=BLOCKED_IR_V2_INCOMPLETE
SELF_EMIT=NOT_STARTED
STAGE2=NOT_STARTED
STAGE3=NOT_STARTED
FULL_SELF_HOSTING=NO
FOCUSED=14_PASSED
COMPILEALL=PASS
JSON_VALIDATION=PASS
DIFF_CHECK=PASS
T4_RUNS_THIS_CAMPAIGN=0
BENCHMARK_RUNS_THIS_CAMPAIGN=0
PRIMARY_BLOCKER=PACKED_TOKEN_VALUE_LANE_CAPACITY_OR_ENCODING_GAP
NEXT=NATIVE_REQUALIFY_REPAIRED_TOKEN_LANE_AND_RESOLVE_FULL_SOURCE_CAPACITY
PR_UPDATED=YES
PUSHED=YES
COMPUTER_SHUTDOWN_REQUESTED=NO
COMPUTER_RESTART_REQUESTED=NO
COMPUTER_LEFT_RUNNING=YES
LINUX_VM_LEFT_RUNNING=YES
```
