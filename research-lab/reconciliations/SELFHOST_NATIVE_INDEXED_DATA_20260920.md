# Native Indexed Data Reconciliation

Date: 2026-09-20

## Provenance

```text
BASE_PR=306
BASE_BRANCH=feat/s3-native-typed-values
BASE_HEAD=889ad59451b8ef6231815b5c02a94c4873f49e4f
BRANCH=feat/s3-native-indexed-data
PR=307
FUNCTIONAL_HEAD=91390c473634ad855327f7a762fecefb1874f7f7
FINAL_CANDIDATE_HEAD=3c125bc5a8ee7cbcf91361f9f632e11265b73e4a
MERGED=NO
DRAFT=YES
```

The campaign built a bounded `NativeIndexedValue` contract on the exact PR
#306 head. It reused existing typed vector payloads and made element kind,
length, mutability, ownership, and lifetime explicit. It did not modify the
protected canonical Stage1 source, PRs 301--306, release metadata, or
S3-Benchmarks.

## Evidence

The local focused contract suite passed six tests. The adjacent semantic and
hosted collection tests, compileall, and diff-check also passed. The one final
full suite ran at the functional source head only:

```text
FULL_SUITE_HEAD=91390c473634ad855327f7a762fecefb1874f7f7
FULL_SUITE=4027 passed, 312 skipped, 0 failed
FULL_SUITE_EXIT=0
FULL_SUITE_START=2026-09-20T14:08:17.7035086-03:00
FULL_SUITE_END=2026-09-20T15:09:57.6944454-03:00
FULL_SUITE_ELAPSED_SECONDS=3699.9909
FULL_SUITE_TRANSCRIPT=scratch/s3-native-indexed-data-full-suite-20260920.txt
```

The probes prove local construction and metadata validation, lengths 0, 1,
and 3, local payload read, and a vector-payload parameter. They do not prove
that a complete indexed value crosses a native function boundary.

## Negative architectural result

The hosted semantic analyzer rejects a reference to the nominal aggregate with
`reference target must be a scalar type`. This is a real boundary in the
current language model. Passing a vector payload and a separate length is not
treated as an aggregate ABI workaround.

```text
NATIVE_INDEXED_VALUE_PROTOCOL=BLOCKED_AT_AGGREGATE_REFERENCE_BOUNDARY
ARCHITECTURAL_BLOCKER=OWNERSHIP_OR_LIFETIME_SEMANTICS_UNDERDEFINED_FOR_BORROWED_AGGREGATE_NATIVE_VALUES
FIRST_MISSING_CAPABILITY=NATIVE_AGGREGATE_REFERENCE_AND_OWNERSHIP_CONTRACT
NATIVE_INDEXED_I64_EXECUTION=BLOCKED
NATIVE_INDEXED_F64_EXECUTION=BLOCKED
NUMERIC_WORKLOAD=NOT_STARTED
SCIENTIFIC_WORKLOAD=NOT_STARTED
REFERENCE_FALLBACK=NONE
```

The missing design must choose and prove either aggregate references or an
explicit ownership/transfer ABI. It must define payload identity, element
type, length, bounds, mutability, ownership, lifetime, aliasing, and return
behavior. Hosted arrays, vectors, and slices are evidence of source-level
semantics only; they do not establish a native aggregate layout.

## Remote status

Draft PR #307 is open against `feat/s3-native-typed-values`. The two natural
workflow runs failed after approximately 2--3 seconds and every job reported
`steps=[]`. They are classified as pre-execution infrastructure dispatch
failures; no remote test executed and no rerun was issued. PR #306 remains open
and unchanged.

```text
REMOTE_CHECKS=FAIL_PRE_EXECUTION
REMOTE_CHECK_CAUSE=INFRA_DISPATCH
REMOTE_CHECK_RUNS=35528321750,35528321753
REMOTE_TEST_EXECUTED=NO
REMOTE_CI_RERUN=NO
```

## Knowledge closure

This negative result strengthens IC-005, IC-008, IC-012, IC-015, and IC-016:
semantic meaning, legal representation, and target realization remain
separate, and an existing hosted collection abstraction cannot be promoted to
a native ABI without explicit ownership and lifetime evidence. IC-014 remains
unchanged because the indexed-data experiment used explicit element kinds and
did not introduce implicit signature or numeric representation inference.

No Zettel is promoted from this checkpoint. The next safe question is the
smallest coherent aggregate-reference and ownership/lifetime contract; indexed
i64/f64 execution and SSD/RMSD workloads remain deferred until that contract
is independently proven.
