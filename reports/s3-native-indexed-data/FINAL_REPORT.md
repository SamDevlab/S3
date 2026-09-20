# Native Indexed Data Campaign

## Scope and provenance

This report records the bounded native indexed-data checkpoint from PR #306.
The campaign starts from the PR #306 head and does not modify PRs 301--306,
S3-Benchmarks, release metadata, or the protected canonical Stage1 source.

```text
SOURCE_BASE_PR=306
SOURCE_BASE_BRANCH=feat/s3-native-typed-values
SOURCE_BASE_HEAD=889ad59451b8ef6231815b5c02a94c4873f49e4f
SOURCE_BASE_STATE=OPEN_DRAFT
SOURCE_BASE_MERGED=NO

NEW_BRANCH=feat/s3-native-indexed-data
NEW_PR=PENDING
NEW_PR_STATE=PENDING
NEW_PR_BASE=feat/s3-native-typed-values
NEW_PR_HEAD=91390c473634ad855327f7a762fecefb1874f7f7
NEW_PR_MERGED=NO

START_HEAD=889ad59451b8ef6231815b5c02a94c4873f49e4f
FINAL_FUNCTIONAL_HEAD=91390c473634ad855327f7a762fecefb1874f7f7
FINAL_HEAD=91390c473634ad855327f7a762fecefb1874f7f7
FINAL_HEAD_DELTA_FROM_FUNCTIONAL_HEAD=NONE
REMOTE_SYNC=NOT_PUSHED_AT_FUNCTIONAL_CHECKPOINT
```

The functional commit is:

```text
91390c473634ad855327f7a762fecefb1874f7f7
feat(selfhost): define bounded indexed value contract
```

## Existing model and selected contract

```text
EXISTING_INDEXED_TYPES=fixed arrays, vectors, slices
SELECTED_INDEXED_TYPE=bounded NativeIndexedValue contract candidate
SELECTED_INDEXED_VALUE_MODEL=owned record with explicit element_kind/length/mutability/ownership/lifetime and parallel i64/f64 vector payloads
ALTERNATIVE_MODELS_EVALUATED=fixed inline array; owned payload+length; borrowed slice/view; fixed array + borrowed slice
WHY_SELECTED=smallest explicit representation reusing existing typed vector payloads without host identity; rejected for call boundary due aggregate-reference rule

ELEMENT_TYPE_MODEL=explicit 1=i64, 2=f64
PAYLOAD_STORAGE_MODEL=owned typed vector field inside NativeIndexedValue
NATIVE_LENGTH_MODEL=explicit length field, validated against payload vector length
COLLECTION_MUTABILITY=explicit 0 immutable / 1 mutable
NATIVE_OWNERSHIP_MODEL=owned payload marker=1; aggregate borrowing not supported
NATIVE_LIFETIME_MODEL=frame-bounded marker=1; cross-call borrowed aggregate lifetime unproven
NATIVE_BOUNDS_BEHAVIOR=local bounds check before vector get; invalid aggregate reference crossing rejected
ALIASING_MODEL=not established; no host behavior inferred
```

The implementation deliberately does not pretend that separate payload and
length parameters constitute a qualified aggregate ABI. The hosted semantic
model rejects a reference to the nominal `NativeIndexedValue` record with:
`reference target must be a scalar type`. Passing the payload vector and its
length separately is retained only as a bounded probe of the already-supported
vector-reference path.

## Capability result

```text
NATIVE_INDEXED_VALUE_PROTOCOL=BLOCKED_AT_AGGREGATE_REFERENCE_BOUNDARY
NATIVE_COLLECTION_CONSTRUCTION=PASS_FOR_LOCAL_RECORD_CONTRACT
NATIVE_COLLECTION_LENGTH=PASS_FOR_0_1_3_LOCAL_CONTRACT
NATIVE_INDEX_READ=PASS_FOR_LOCAL_PAYLOAD_PROBE_ONLY
NATIVE_INDEX_WRITE=NOT_IMPLEMENTED; aggregate mutation crossing is not qualified
NATIVE_INDEXED_LOCAL=PASS_FOR_LOCAL_RECORD_AND_PAYLOAD_PROBES
NATIVE_INDEXED_PARAMETER=PAYLOAD_ONLY; whole collection blocked
NATIVE_INDEXED_RETURN=NOT_CLAIMED; cross-boundary lifetime is unqualified
NATIVE_INDEXED_I64_EXECUTION=BLOCKED_BEFORE_COHERENT_COLLECTION_CALL_MODEL
NATIVE_INDEXED_F64_EXECUTION=BLOCKED

I64_REGRESSION=NONE
F64_REGRESSION=NONE
FIRST_REAL_PROGRAM_RESULT=42
REFERENCE_FALLBACK=NONE
ANTI_FALLBACK_TESTS=PASS
DIFFERENTIAL_EXECUTION=NOT_REACHED; local native contract probes only
```

The first real architectural blocker is:

```text
ARCHITECTURAL_BLOCKER=OWNERSHIP_OR_LIFETIME_SEMANTICS_UNDERDEFINED_FOR_BORROWED_AGGREGATE_NATIVE_VALUES
FIRST_MISSING_CAPABILITY=NATIVE_AGGREGATE_REFERENCE_AND_OWNERSHIP_CONTRACT
```

The current semantic model permits references to scalar, dynamic, and vector
targets, but not to this nominal aggregate. A coherent collection value cannot
cross a function boundary with its metadata and payload as one value until the
language defines either aggregate references or an explicit ownership/transfer
ABI. Extending that model is a separate architectural change, not a local
indexed-data lowering fix.

## Numeric and scientific workload status

```text
S3_NUMERIC_WORKLOAD_0_1=NOT_STARTED; blocked by aggregate call boundary
NUMERIC_WORKLOAD_KIND=SUM_OF_SQUARED_DIFFERENCES
NUMERIC_WORKLOAD_INPUT=NOT_EXECUTED
NUMERIC_WORKLOAD_RESULT=NOT_AVAILABLE

EXISTING_MATH_MODEL=No existing sqrt builtin was found in the repository search
MATH_PRIMITIVE_MODEL=NOT_REACHED
NATIVE_SQRT=DEFERRED

S3_SCIENTIFIC_WORKLOAD_0_1=NOT_STARTED; blocked by aggregate call boundary
SCIENTIFIC_WORKLOAD_KIND=RMSD_MINIMAL
SCIENTIFIC_WORKLOAD_RESULT=NOT_AVAILABLE
SCIENTIFIC_WORKLOAD_TOLERANCE=NOT_DEFINED
READY_FOR_INDEPENDENT_BENCHMARKING=NO
```

No numeric or scientific workload result is claimed. No host fallback, fake
indexed execution, implicit coercion, GC, or type inference was introduced.

## Validation evidence

```text
WINDOWS_FOCUSED=PASS
INDEXED_CHECKPOINT_TESTS=PASS_FOR_CONTRACT_LOCAL_PROBES_AND_BLOCKER
SEMANTIC_CHECKPOINT_TESTS=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS

FULL_SUITE=4027 passed, 312 skipped, 0 failed
FULL_SUITE_SHA=91390c473634ad855327f7a762fecefb1874f7f7
FULL_SUITE_START=2026-09-20T14:08:17.7035086-03:00
FULL_SUITE_END=2026-09-20T15:09:57.6944454-03:00
FULL_SUITE_ELAPSED_SECONDS=3699.9909
FULL_SUITE_EXIT=0
FULL_SUITE_TRANSCRIPT=scratch/s3-native-indexed-data-full-suite-20260920.txt

NATIVE_LINUX_QUALIFICATION=DEFERRED_TO_LINUX_HOST
NATIVE_LINUX_TEST_COUNT=0
NATIVE_LINUX_INDEXED_WORKLOAD=DEFERRED
NATIVE_LINUX_NUMERIC_WORKLOAD=DEFERRED
NATIVE_LINUX_SCIENTIFIC_WORKLOAD=DEFERRED
REMOTE_CHECKS=NOT_RUN_BEFORE_DRAFT_PR
```

The focused and adjacent command was:

```text
python -m compileall bootstrap/s3
python -m pytest tests/test_native_indexed_data.py tests/test_native_semantic_execution.py tests/test_m140_ordered_collections.py tests/test_m155_generic_vector.py tests/test_m162_composite_vectors.py -q
git diff --check
```

The focused test file contains six passing tests, including the explicit
aggregate-reference blocker assertion and no-host-fallback checks.

## Changed files

The functional checkpoint changes only:

```text
selfhost/substrate/native_indexed_value_protocol.s3
tests/test_native_indexed_data.py
```

Documentation after the functional checkpoint is permitted without rerunning
the full suite. No merge, release, tag, PyPI publication, or benchmark was
performed.

## Knowledge closure

This checkpoint strengthens the existing research conclusions that semantic
value meaning, legal representation, and target realization must remain
separate. It specifically confirms that hosted vector references do not prove
an aggregate native ABI, and that ownership and lifetime must be explicit
before collection values are passed or returned across native function
boundaries. The result reinforces IC-005, IC-008, IC-012, IC-015, and IC-016;
IC-014 remains deferred and unchanged.

The next safe research target is an explicit aggregate-reference and
ownership/lifetime contract. It must be designed and tested before indexed
i64/f64 execution or SSD/RMSD workloads can be claimed.
