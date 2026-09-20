# Native Typed Value Protocol Campaign

## Provenance

```text
SOURCE_BASE_PR=305
SOURCE_BASE_BRANCH=feat/s3-native-semantic-execution
SOURCE_BASE_HEAD=48f2551c130ba29e6becf63aba2d4e57c69d35c6
SOURCE_FUNCTIONAL_HEAD=34a923f84db7ff8d4f9b7cf9083f272169cc7524
SOURCE_BASE_STATE=OPEN_DRAFT
SOURCE_BASE_MERGED=NO

NEW_BRANCH=feat/s3-native-typed-values
START_HEAD=48f2551c130ba29e6becf63aba2d4e57c69d35c6
FINAL_FUNCTIONAL_HEAD=cc05357ad6e72c3bc13032b1ed55303be93f2661
FINAL_HEAD=f3b91bba9e7b98a7131ace8c4c7ea7945cca2392
FINAL_HEAD_DELTA_FROM_FUNCTIONAL_HEAD=DOCS_ONLY
NEW_PR=306
NEW_PR_STATE=OPEN_DRAFT
NEW_PR_BASE=feat/s3-native-semantic-execution
NEW_PR_HEAD=f3b91bba9e7b98a7131ace8c4c7ea7945cca2392
NEW_PR_MERGED=NO
REMOTE_SYNC=origin/feat/s3-native-typed-values at f3b91bba9e7b98a7131ace8c4c7ea7945cca2392
```

The functional commit contains only the typed-value implementation and its
focused tests. The protected canonical source was not changed.

## Architecture

```text
CURRENT_NATIVE_VALUE_REPRESENTATION=parallel i64-only vectors before this campaign
CURRENT_LOCAL_ENVIRONMENT_REPRESENTATION=i64 name/value bindings before this campaign
CURRENT_PARAMETER_REPRESENTATION=i64 parameter values before this campaign
CURRENT_RETURN_REPRESENTATION=vector carrying function start and i64 value before this campaign
CURRENT_BINARY_OP_MODEL=i64-only operator evaluation
CURRENT_COMPARISON_MODEL=branch-coded comparison results
CURRENT_CALL_RESULT_MODEL=i64 function result
CURRENT_WHILE_CONDITION_MODEL=i64 condition result

SELECTED_TYPED_VALUE_MODEL=parallel type tag plus typed payload fields
ALTERNATIVE_MODELS_EVALUATED=tagged union; separate typed value paths; parallel tag and payload
WHY_SELECTED=smallest explicit model preserving i64 while adding f64 and rejecting mismatches without dynamic coercion

NATIVE_VALUE_PROTOCOL=PASS
NATIVE_RESULT_PROTOCOL=PASS
NATIVE_RESULT_ERROR_MODEL=distinct status values: value=1, error=0, no-return=-1
```

`NativeTypedValue` carries explicit kind, i64 payload, and f64 payload.
`NativeTypedResult` carries status, next cursor, and typed value. Locals,
parameters, calls, returns, operators, and while conditions use this protocol.
The protocol is typed execution infrastructure, not a dynamic type system.

## Scalar evidence

```text
I64_PRE_TYPED_PROTOCOL_RESULT=42
I64_POST_TYPED_PROTOCOL_RESULT=42
I64_REGRESSION=NONE
NATIVE_I64_SEMANTIC_EXECUTION=PASS
FIRST_REAL_PROGRAM_RESULT=42

NATIVE_F64_TOKENIZATION=PASS
NATIVE_F64_VALUE=PASS
NATIVE_F64_LOCAL=PASS
NATIVE_F64_ASSIGNMENT=PASS
NATIVE_F64_PARAMETERS=PASS
NATIVE_F64_FUNCTION_CALL=PASS
NATIVE_F64_RETURN=PASS
NATIVE_F64_SCALAR_EXECUTION=PASS
FLOAT_RESULT_COMPARISON=exact known result 4.75
NUMERIC_COERCION_POLICY=none; mixed i64/f64 binary operations reject closed
```

The native lexer gives decimal literals a distinct token kind. The f64
fixture executes `add(a: f64, b: f64) -> f64`, a local assignment, a second
f64 assignment, and a return. The mixed-type negative test confirms that
`i64 + f64` does not silently coerce.

## Indexed and workload frontier

The hosted semantic model already has fixed arrays and slices, including
length metadata, bounds behavior, mutability, and copy/reference distinctions.
The native typed protocol does not yet carry collection payload, element type,
length, bounds, or ownership/lifetime information.

```text
EXISTING_INDEXED_DATA_TYPE=fixed arrays and slices in the hosted semantic model
ELEMENT_TYPE_MODEL=hosted element types are explicit; native collection model not defined
LENGTH_MODEL=hosted fixed length or slice length; native length payload not defined
OWNERSHIP_MODEL=hosted fixed-array copy and slice reference metadata
MUTABILITY_MODEL=hosted slice mutability; native collection mutability not defined
BOUNDS_MODEL=hosted bounds checks pass; native indexed checks unavailable
LAYOUT_MODEL=hosted fixed-layout cells and slice metadata; native layout not defined

NATIVE_INDEXED_DATA_LAYOUT=not defined for typed native protocol
NATIVE_INDEXED_DATA=BLOCKED_ARCHITECTURALLY
NATIVE_INDEX_READ=DEFERRED
NATIVE_BOUNDS_BEHAVIOR=hosted PASS; native unavailable
NATIVE_OWNERSHIP_MODEL=hosted fixed-array copy/slice reference metadata; native contract missing

S3_NUMERIC_WORKLOAD_0_1=NOT_STARTED/BLOCKED
NUMERIC_WORKLOAD_KIND=small f64 indexed sum-of-squared-differences; not executed
NUMERIC_WORKLOAD_INPUT=not applicable
NUMERIC_WORKLOAD_EXPECTED=not applicable
NUMERIC_WORKLOAD_RESULT=not available

MATH_PRIMITIVE_MODEL=not investigated because indexed native representation is first blocker
NATIVE_SQRT=DEFERRED

S3_SCIENTIFIC_WORKLOAD_0_1=NOT_STARTED/BLOCKED
SCIENTIFIC_WORKLOAD_KIND=small RMSD-style workload; not executed
SCIENTIFIC_WORKLOAD_EXPECTED=not applicable
SCIENTIFIC_WORKLOAD_RESULT=not available
SCIENTIFIC_WORKLOAD_TOLERANCE=not defined
SCIENTIFIC_WORKLOAD_READINESS=BLOCKED_ARCHITECTURALLY
```

The first missing capability is a native indexed-value layout and
ownership/bounds protocol. No array, heap, or scientific workload was faked.

## Validation

```text
REFERENCE_FALLBACK=NONE
ANTI_FALLBACK_TESTS=PASS
DIFFERENTIAL_EXECUTION=hosted-vs-native scalar evidence; indexed workload not available

HOST_EXECUTION_SUPPORT=Windows hosted/emulator; Linux native not available on this host
HOST_SEMANTIC_DECISIONS=explicit typed native values/results
WINDOWS_FOCUSED=PASS
SEMANTIC_CHECKPOINT_TESTS=PASS

PR305_LINUX_SEMANTIC_QUALIFICATION=NOT_EXECUTED_ON_WINDOWS
NATIVE_LINUX_QUALIFICATION=DEFERRED
NATIVE_LINUX_TEST_COUNT=0
NATIVE_LINUX_NUMERIC_WORKLOAD=DEFERRED
NATIVE_LINUX_SCIENTIFIC_WORKLOAD=DEFERRED

FULL_SUITE=4021 passed, 312 skipped, 0 failed
FULL_SUITE_START=2026-09-20T12:36:35.8032936-03:00
FULL_SUITE_END=2026-09-20T13:43:21.4070107-03:00
FULL_SUITE_ELAPSED_SECONDS=4005.6037171
FULL_SUITE_SHA=cc05357ad6e72c3bc13032b1ed55303be93f2661
FULL_SUITE_TRANSCRIPT=scratch/s3-native-typed-values-full-suite-20260920.txt

COMPILEALL=PASS
DIFF_CHECK=PASS
REMOTE_CHECKS=NOT_RUN_YET
REMOTE_FAILURE_CAUSE=NOT_APPLICABLE
RUNNER_ASSIGNED=NO
STEPS_STARTED=local only
REMOTE_TEST_EXECUTED=NO
REMOTE_CI_RERUN=NO
S3_BENCHMARKS_CHANGED=NO
```

The full suite was run exactly once at the final functional HEAD. The two
scratch transcripts remain untracked evidence and were not included in the
functional commit.

## Blocker and next decision

```text
ARCHITECTURAL_BLOCKER=NATIVE_INDEXED_VALUE_LAYOUT_AND_OWNERSHIP_PROTOCOL
FIRST_MISSING_CAPABILITY=NATIVE_INDEXED_VALUE_PAYLOAD_LENGTH_BOUNDS_OWNERSHIP_CONTRACT
MINIMUM_NEXT_DESIGN_DECISION=define native fixed-array/slice representation and ownership/bounds protocol before index execution
```

The scalar result answers the primary question positively: explicit typed
native values let i64 and f64 share one coherent scalar execution model.
The indexed-data question remains open: adding native indexed values requires
an explicit layout and ownership contract; the hosted model cannot be reused
as an implementation shortcut. The scientific workload requirements therefore
select the next minimum capability without changing the language.

## Knowledge closure

```text
KNOWLEDGE_CLOSURE=scalar typed value identity is an explicit boundary; indexed data is a separate native representation boundary
RESEARCH_RECONCILIATION_FILE=research-lab/reconciliations/SELFHOST_NATIVE_TYPED_VALUES_20260920.md
RESEARCH_STATE_UPDATED=YES; research commit 6becd1ea
RESEARCH_HANDOFF_UPDATED=YES; research commit 6becd1ea
INSIGHT_CANDIDATES_STRENGTHENED=IC-005, IC-008, IC-012, IC-015, IC-016
INSIGHT_CANDIDATES_WEAKENED=IC-014 unchanged; type inference remains separate
NEW_ZETTELS=NONE
NEW_NEGATIVE_RESULTS=native indexed layout/ownership is not implied by hosted arrays and slices

WHAT_WORKED=explicit typed value/result protocol preserved i64 and executed f64 scalar calls, locals, assignment, and returns
WHAT_FAILED=not applicable to scalar path; indexed native execution could not be claimed
WHAT_WAS_FALSIFIED=an i64-only vector result is not sufficient as a multi-representation native value contract
WHAT_REMAINS_UNKNOWN=native indexed layout, bounds, ownership/lifetime, Linux qualification, numeric workload, scientific workload
```

## Publication state

```text
FILES_CHANGED=functional: generic_lexer_state.s3, native_semantic_execution.s3, native_typed_value_protocol.s3, tests/test_native_semantic_execution.py; documentation: this report
COMMITS_CREATED=cc05357ad6e72c3bc13032b1ed55303be93f2661; 8984b67cd30f6d84f903335262b35dbe5e1a4886; f3b91bba9e7b98a7131ace8c4c7ea7945cca2392
PUSHED=YES
CODE_READY=YES for scalar typed protocol
CI_READY=NO until Draft PR natural checks are observed
READY_FOR_BASE_MERGE=NO
NEXT_CAMPAIGN_OR_BLOCKER=define and prove the native indexed value/layout/ownership protocol
```

No merge, release, tag, PyPI publication, or benchmark change is part of
this campaign. PR305 remains untouched.
