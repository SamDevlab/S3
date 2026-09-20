# Native Aggregate References and Indexed Scientific Workload

This report closes the bounded campaign started from PR #307. It records the
first safe aggregate-reference implementation and the first real blocker after
the SSD workload.

## Provenance

```text
SOURCE_BASE_PR=307
SOURCE_BASE_BRANCH=feat/s3-native-indexed-data
SOURCE_BASE_HEAD=86dccea0d1e1499578005f7e3f89a46fd3afd2ed
SOURCE_FUNCTIONAL_HEAD=91390c473634ad855327f7a762fecefb1874f7f7

NEW_BRANCH=feat/s3-native-aggregate-references
NEW_PR=308
NEW_PR_STATE=OPEN_DRAFT
NEW_PR_BASE=feat/s3-native-indexed-data
NEW_PR_HEAD=59a27730bd6dd9ba3526fed160182dee8054d1d9
NEW_PR_MERGED=NO

START_HEAD=86dccea0d1e1499578005f7e3f89a46fd3afd2ed
FINAL_FUNCTIONAL_HEAD=fd4cf580e61cd82b6c49425d0ee9d34d3573de8b
FINAL_HEAD=59a27730bd6dd9ba3526fed160182dee8054d1d9
FINAL_HEAD_DELTA_FROM_FUNCTIONAL_HEAD=TEST_CONTRACT_ONLY
SOURCE_CHANGED_AFTER_FULL_SUITE=NO
REMOTE_SYNC=YES
```

The functional commit is `fd4cf580`, `feat(selfhost): add bounded aggregate
reference execution`. Commit `59a27730` only updates exhaustive opcode test
contracts after the one permitted full-suite run. PR URL:
https://github.com/SamDevlab/S3/pull/308

## Semantic contract

```text
SCALAR_REFERENCE_MODEL=scalar and vector references with existing call checks
WHY_SCALAR_ONLY=IR, lowering, verifier and runtime previously assumed that a reference was one scalar cell or an existing vector view
WHAT_CHANGED=only known nominal records are accepted as immutable aggregate reference targets
SCALAR_REFERENCE_REGRESSION=NONE

EXISTING_AGGREGATE_TYPES=records, fixed arrays, vectors, slices, owned dynamic values
EXISTING_SLICE_MODEL=borrowed slices with explicit length, mutability and bounds checks
EXISTING_OWNED_DATA_MODEL=typed owned vector payloads with runtime bounds checks

CANDIDATE_REFERENCE_MODELS=read-only call-bounded aggregate borrow; mutable aggregate borrow; owned transfer; aggregate return
SELECTED_REFERENCE_MODEL=read-only call-bounded aggregate borrow
WHY_SELECTED=the smallest model sufficient for indexed numeric reads and scalar returns

NATIVE_AGGREGATE_REFERENCE_TYPE=PASS_FOR_KNOWN_RECORD_TARGETS
NATIVE_AGGREGATE_REFERENCE_VALUE=one IR reference value with aggregate identity and field-cell paths
AGGREGATE_PAYLOAD_IDENTITY=stable semantic record identity represented by the referenced frame cells; no host list identity
AGGREGATE_ELEMENT_TYPE=explicit record metadata and typed vector fields preserve i64 or f64
AGGREGATE_LENGTH_MODEL=explicit length field paired with the same aggregate reference identity

AGGREGATE_MUTABILITY_MODEL=owner binding may be mutable, but the supported aggregate borrow is immutable
AGGREGATE_OWNERSHIP_MODEL=caller/local owns the record and its payload fields; callee borrows
AGGREGATE_BORROW_MODEL=read-only borrow across one call
AGGREGATE_LIFETIME_MODEL=call-bounded; active borrow is restored after call analysis
AGGREGATE_ALIASING_MODEL=multiple read-only borrows are allowed; mutation through this reference is rejected

BORROW_START=address-of at the call site
BORROW_END=return from the call
BORROW_ESCAPE_ALLOWED=NO
MUTABLE_AGGREGATE_BORROW=DEFERRED_NOT_REQUIRED_AND_REJECTED
OWNED_AGGREGATE_TRANSFER=DEFERRED_NOT_REQUIRED
AGGREGATE_RETURN=DEFERRED_NOT_REQUIRED
```

The former scalar-only rule protected assumptions that a reference result fit
one storage cell, that verifier type identity was scalar, and that call
lowering could pass one reference without aggregate provenance. The repair
extends each of those layers together. It does not accept arbitrary arrays,
unknown nominal types, mutable aggregate references, escaping aggregate
references, or aggregate returns.

## Boundary and indexed execution

```text
AGGREGATE_CROSSES_FUNCTION_BOUNDARY=PASS
PAYLOAD_IDENTITY_PRESERVED=PASS
ELEMENT_TYPE_PRESERVED=PASS
LENGTH_PRESERVED=PASS
CALLER_OWNER=local NativeIndexedValue
CALLEE_REFERENCE=one &NativeIndexedValue parameter

NATIVE_BOUNDS_BEHAVIOR=payload access uses the referenced aggregate payload and its bounds-checked vector operation
NATIVE_INDEX_READ=PASS
NATIVE_INDEXED_I64_EXECUTION=PASS_FOR_NATIVE_S3_IR_PATH
NATIVE_INDEXED_F64_EXECUTION=PASS_FOR_NATIVE_S3_IR_PATH

I64_REGRESSION=NONE
F64_REGRESSION=NONE
NUMERIC_COERCION_POLICY=NONE
```

The tests cover length, first/middle/last reads through a borrowed aggregate,
out-of-bounds rejection, two calls using the same owner, i64 accumulation,
f64 accumulation, and preservation of the owner after a callee returns. The
aggregate is represented as one semantic reference; payload and length are not
two independent call parameters. The IR, verifier and hosted S3 emulator carry
the aggregate identity. The x86 emitter does not yet qualify `TAGG*`, so no
Linux native claim is made.

## Numeric workload

```text
S3_NUMERIC_WORKLOAD_0_1=PASS
NUMERIC_WORKLOAD_KIND=SSD
NUMERIC_WORKLOAD_INPUT=A=[1.0,2.0,3.0], B=[2.0,4.0,6.0], equal length 3
NUMERIC_WORKLOAD_EXPECTED=14.0
NUMERIC_WORKLOAD_RESULT=14.0
SSD_MISMATCHED_LENGTH_BEHAVIOR=explicit -1.0 result without reading past either payload
```

The SSD fixture receives two aggregate references and computes
`sum((A[i]-B[i])*(A[i]-B[i]))` only after checking equal lengths. This is a
correctness result, not a performance claim.

## Math and scientific frontier

```text
EXISTING_MATH_MODEL=no sqrt builtin, intrinsic, runtime helper, libm path or backend operation found
MATH_PRIMITIVE_MODEL=ABSENT
NATIVE_SQRT=BLOCKED

S3_SCIENTIFIC_WORKLOAD_0_1=BLOCKED
SCIENTIFIC_WORKLOAD_KIND=RMSD_MINIMAL
SCIENTIFIC_WORKLOAD_FORMULA=sqrt(sum((A[i]-B[i])^2) / point_count)
SCIENTIFIC_WORKLOAD_INPUT=NOT_EXECUTED
SCIENTIFIC_WORKLOAD_EXPECTED=NOT_AVAILABLE
SCIENTIFIC_WORKLOAD_RESULT=NOT_AVAILABLE
SCIENTIFIC_WORKLOAD_TOLERANCE=NOT_DEFINED
READY_FOR_INDEPENDENT_BENCHMARKING=NO

ARCHITECTURAL_BLOCKER=NATIVE_MATH_PRIMITIVE_CONTRACT
FIRST_MISSING_CAPABILITY=MINIMAL_F64_SQRT_SEMANTIC_IR_RUNTIME_BACKEND_CONTRACT
MINIMUM_NEXT_DESIGN_DECISION=define and qualify one f64 sqrt primitive under the existing #306 numeric policy before implementing RMSD
```

The blocker is factual: repository search found no existing sqrt builtin,
intrinsic, runtime helper, libm binding, IR opcode, or backend path. The
campaign stops here rather than implementing an ad hoc math library or using a
Python math fallback.

## Anti-fallback and platform evidence

```text
REFERENCE_FALLBACK=NONE
ANTI_FALLBACK_TESTS=PASS
DIFFERENTIAL_EXECUTION=semantic invariants and IR/emulator result; no host collection semantics used
HOST_EXECUTION_SUPPORT=Python harness hosts parsing/lowering and executes the S3 IR emulator
HOST_SEMANTIC_DECISIONS=NONE for aggregate identity, ownership, borrow lifetime, bounds and workload arithmetic

WINDOWS_FOCUSED=PASS
AGGREGATE_REFERENCE_CHECKPOINT_TESTS=PASS
INDEXED_CHECKPOINT_TESTS=PASS
NUMERIC_WORKLOAD_TESTS=PASS
SCIENTIFIC_WORKLOAD_TESTS=NOT_RUN_AFTER_REAL_SQRT_BLOCKER

NATIVE_LINUX_AGGREGATE_REFERENCE=DEFERRED
NATIVE_LINUX_INDEXED_I64=DEFERRED
NATIVE_LINUX_INDEXED_F64=DEFERRED
NATIVE_LINUX_SSD=DEFERRED
NATIVE_LINUX_RMSD=DEFERRED
NATIVE_LINUX_TEST_COUNT=0
```

## Validation

```text
COMPILEALL=PASS
DIFF_CHECK=PASS
FOCUSED_AND_ADJACENT_TESTS=PASS
FOCUSED_REPAIR_TESTS=PASS

FULL_SUITE_HEAD=fd4cf580e61cd82b6c49425d0ee9d34d3573de8b
FULL_SUITE_RUNS=1
FULL_SUITE=3 stale exhaustive opcode-contract failures
FULL_SUITE_EXIT=1
FULL_SUITE_START=2026-09-20T16:44:40.1256119-03:00
FULL_SUITE_END=2026-09-20T18:01:20.6439378-03:00
FULL_SUITE_TRANSCRIPT=scratch/s3-native-aggregate-references-full-suite-20260920.txt
FULL_SUITE_TRANSCRIPT_SHA256=17004918be8fbfe67e2ded685044dfdd57aad7fcf330c21dd097fb44b128792f
FULL_SUITE_RERUN=NO_BY_ONE_RUN_POLICY
POST_SUITE_TARGETED_REPAIR=PASS
```

The three full-suite failures were stale exact-enum expectations in
`tests/test_compiler.py`, `tests/test_s3_static_text_concatenation_ir.py`,
and `tests/test_native_x86_64.py`. The targeted tests passed after adding the
three IR opcodes and explicitly excluding the still-unqualified aggregate
assembly opcodes from the x86 emitter inventory. The functional source was
unchanged after the full suite; no second full suite was run.

## Research closure

```text
S3_BENCHMARKS_CHANGED=NO
BIOLAB_REPOSITORY_CHANGED=NO
REMOTE_CHECKS=FAIL_PRE_EXECUTION
REMOTE_FAILURE_CAUSE=INFRA_DISPATCH
REMOTE_CHECKS_HEAD=9c64308d9faa51b95daa26d5aad6958456065589
REMOTE_CHECKS_RUNS=35537769371,35537769386
RUNNER_ASSIGNED=NO_STEPS_STARTED
STEPS_STARTED=NO
REMOTE_TEST_EXECUTED=NO
REMOTE_CI_RERUN=NO

KNOWLEDGE_CLOSURE=COMPLETE_FOR_AGGREGATE_REFERENCE_AND_SSD_FRONTIER
RESEARCH_RECONCILIATION_FILE=research-lab/reconciliations/SELFHOST_NATIVE_AGGREGATE_REFERENCES_20260920.md
RESEARCH_STATE_UPDATED=YES
RESEARCH_HANDOFF_UPDATED=YES
RESEARCH_LOCATOR_UPDATED=YES
INSIGHT_CANDIDATES_STRENGTHENED=IC-003, IC-005, IC-008, IC-012, IC-015, IC-016
INSIGHT_CANDIDATES_WEAKENED=none
NEW_ZETTELS=none pending independent review
NEW_NEGATIVE_RESULTS=sqrt primitive absent; native x86 aggregate emitter unqualified

REFERENCE_MODELS_REJECTED=
mutable aggregate borrow: not required and unsafe to add without a write contract;
owned transfer: unnecessary for read-only SSD/RMSD;
aggregate return: unnecessary and would expand lifetime obligations;
payload-plus-length ABI: rejected as semantically split

WHAT_WORKED=known-record immutable call-bounded aggregate references reuse existing borrow and vector bounds mechanisms
WHAT_FAILED=full-suite exact opcode inventories and the next RMSD math primitive gate
WHAT_WAS_FALSIFIED=hosted vector references alone do not prove an aggregate native ABI
WHAT_REMAINS_UNKNOWN=Linux x86 aggregate emission, a qualified sqrt contract, RMSD and independent native performance
```

```text
COMMITS_CREATED=fd4cf580, 59a27730
PUSHED=YES_TO_NEW_BRANCH_ONLY
CODE_READY=YES_FOR_SUPPORTED_HOSTED_IR_SCOPE
CI_READY=UNQUALIFIED
READY_FOR_BASE_MERGE=NO
NEXT_CAMPAIGN_OR_BLOCKER=NATIVE_MATH_PRIMITIVE_CONTRACT
```

No merge, release, tag, PyPI publication, benchmark, S3-Benchmarks change,
Biolab change, or shutdown was performed.
