# S3 1.2 Composite Vector Representability

Date: 2026-09-17
Base main: `1e978b0d988f999d31ad15bdd6889393043e906a`
Start HEAD: `4f70ce13934a9b4f3cfdecab22d17a973b555f5d`
Final tested HEAD: `2a59d38dca6f40d126d9797e753a803a1d07db2b`
Implementation commit: `ab891b2b`
Status: `IMPLEMENTED_NATIVE_LINUX_X86_64_FOCUSED_VERIFIED`

This report records the native x86-64 closure of the existing generic
composite-vector contract. It does not authorize a self-hosted compiler,
Stage1 V4, Stage2, a release, or a new collection feature.

## Contract and ABI

`vector<T>` uses the existing semantic `VectorType`, specialization identity,
and `fixed_value_layout` metadata. The lowerer and native backend do not
reconstruct a second layout. For every eligible element type, the layout
determines the ordered cell types, cell count, fixed stride, and owned-leaf
behavior.

The native path extends the existing logical-cell CALL convention. Composite
indexed results use the existing hidden-sret aggregate convention, including
one-cell composite results at the native boundary. Composite runtime wrappers
are deterministic and are selected from decoded specialized signatures, not
from source or fixture names. Storage is bounded and sized as checked
`capacity * element_cell_width`.

`NEW_PUBLIC_ABI=NO`
`ASSEMBLY_FORMAT_CHANGE=NO`
`NATIVE_ABI_DETERMINISM=PASS`

The native runtime validates element cells and bounds, rejects invalid strides
and impossible storage sizes, and keeps failed operations fail-closed. Clone
deep-copies supported owned text/bytes leaves. Replacement validates incoming
cells before disposing of the previous live value. Move and post-drop state
remain invalid according to the existing ownership rules.

## Native matrix

The exact Linux x86-64 focused file collected 75 tests and passed all 75 with
zero skips. The matrix covers O0 and O1 hosted/native agreement for records,
nested records, enums, parametric records, parametric enums, fixed arrays, and
records with owned text. It also covers multiple vector types, replacement,
clone, slice, move, length/capacity/reserve, deterministic assembly, capacity
failure, out-of-bounds failure, and use-after-move rejection.

`RECORD_NATIVE=PASS`
`NESTED_RECORD_NATIVE=PASS`
`ENUM_NATIVE=PASS`
`PARAMETRIC_RECORD_NATIVE=PASS`
`PARAMETRIC_ENUM_NATIVE=PASS`
`FIXED_ARRAY_NATIVE=PASS`
`OWNED_TEXT_COMPOSITE_NATIVE=PASS`

`PUSH_NATIVE=PASS`
`READ_NATIVE=PASS`
`REPLACE_NATIVE=PASS`
`CLONE_NATIVE=PASS`
`MOVE_NATIVE=PASS`

The repository contract confirms that the current language surface has no
generic source-level `vector_drop` builtin: `bootstrap/s3/dynamic.py` exposes
`DynamicCompositeVector.drop()` as a hosted runtime method, while the source
operation table in `bootstrap/s3/ir_emulator.py` has no `vector_drop` entry.
The native runtime has internal recursive descriptor cleanup. Because the
public source operation is not exposed by the current contract, it is not
claimed as a new source-level native API:

`DROP_NATIVE=SOURCE_CONTRACT_NOT_EXPOSED`

`CAPACITY_FAILURE_NATIVE=PASS`
`OOB_FAILURE_NATIVE=PASS`
`USE_AFTER_MOVE_NATIVE=PASS`

## Differential corpus and soak

The deterministic corpus contains 64 meaningful programs: eight each for
pair read, pair replacement, pair clone, pair slice, enum, parametric record,
parametric enum, and fixed-array elements. The cases execute on both O0 and O1
and compare hosted results with native Linux execution.

`DIFFERENTIAL_CASES=64`
`DIFFERENTIAL_PASS=64`
`DIFFERENTIAL_FAIL=0`
`SOAK_PASSES=3`
`SOAK_NONDETERMINISM=0`

Each soak pass ran in a clean process and passed all 75 focused tests. The
specialization identities, generated native assembly, policy outcome, native
exit status, and observable results were stable.

## Compact EA

Baseline native execution passed. Composite-vector programs are not eligible
for Compact EA because the existing policy detects reference operations; the
explicit Compact EA request correctly fell back to baseline and the resulting
native execution passed.

`BASELINE_NATIVE=PASS`
`COMPACT_EA_NATIVE=NOT_APPLICABLE`
`COMPACT_EA_FALLBACK=PASS`
`COMPACT_EA_FALLBACK_REASON=reference_operations_present`

## Validation

`COMPILEALL=PASS`
`DIFF_CHECK=PASS`

Windows development focused tests passed with the expected non-Linux native
skips. The previously executed Windows full suite completed with exit 0 on
the stabilized implementation source; its quiet terminal run recorded 3383
collected tests but did not decompose passed versus skipped counts.

`WINDOWS_SELECTED=3383`
`WINDOWS_PASSED=NOT_DECOMPOSED_IN_QUIET_RUN`
`WINDOWS_SKIPPED=NOT_DECOMPOSED_IN_QUIET_RUN`
`WINDOWS_FAILED=0`
`WINDOWS_EXIT=0`

The valid Linux full-suite run completed with exit 0 on the same production
source implementation before the final test-only corpus expansion. The later
changes were limited to the native test file and were validated by the exact
75-test Linux focused run and three-pass soak.

`LINUX_NATIVE_SELECTED=75`
`LINUX_NATIVE_PASSED=75`
`LINUX_NATIVE_SKIPPED=0`
`LINUX_NATIVE_FAILED=0`
`LINUX_FULL_EXIT=0`
`LINUX_FULL_COUNTS=NOT_DECOMPOSED_IN_QUIET_RUN`

The guest used Python 3.14.4 because a repository-supported Python 3.13.x
interpreter was unavailable. This is supplemental evidence, not a claim of
Python 3.13 certification:

`LINUX_PYTHON_VERSION=3.14.4`
`LINUX_SUPPORTED_PYTHON_CERTIFICATION=BLOCKED_3_13_UNAVAILABLE`

GitHub Actions for the prior remote PR head failed before executing their
steps because the configured runner infrastructure was unavailable. No
repeated CI rerun or unrelated workflow repair was performed here:

`CI_STATE=INFRASTRUCTURE_BLOCKED_PRE_EXECUTION`

## Representability matrix

`REPRESENTABLE_NOW` means that the current language/runtime feature supports
the bounded value shape. It does not mean that the full compiler is written
in S3.

| Structure | Classification | Boundary |
| --- | --- | --- |
| SourceView / bounded source transport | PARTIALLY_REPRESENTABLE | Bounded scalar/text values exist; generic source-file transport is outside this increment. |
| Token | REPRESENTABLE_NOW | Composite record with owned text passes native O0/O1 execution. |
| AST/HIR Node | PARTIALLY_REPRESENTABLE | Flat ID-bearing records and enum payloads are supported; a complete syntax arena is not qualified. |
| ScopeId | REPRESENTABLE_NOW | Bounded `i64` IDs and scalar vectors are supported. |
| Scope | PARTIALLY_REPRESENTABLE | Record storage is supported; general text-keyed lookup is not. |
| DeclarationId | REPRESENTABLE_NOW | Bounded `i64` IDs are supported. |
| Declaration | PARTIALLY_REPRESENTABLE | Composite record storage is supported; full declaration metadata is not qualified. |
| TypeId | REPRESENTABLE_NOW | Bounded `i64` IDs are supported. |
| TypeInfo | PARTIALLY_REPRESENTABLE | Parametric and enum value shapes are supported; recursive metadata and lookup are incomplete. |
| FunctionId | REPRESENTABLE_NOW | Bounded `i64` IDs are supported. |
| StorageId | REPRESENTABLE_NOW | Bounded `i64` IDs are supported. |
| BlockId | REPRESENTABLE_NOW | Bounded `i64` IDs are supported. |
| Block | PARTIALLY_REPRESENTABLE | Flat integer relationships are supported; complete CFG arena behavior is not qualified. |
| ValueId | REPRESENTABLE_NOW | Bounded `i64` IDs are supported. |
| InstructionId | REPRESENTABLE_NOW | Bounded `i64` IDs are supported. |
| Instruction | PARTIALLY_REPRESENTABLE | Fixed fields and arrays are supported; complete generic instruction metadata is not qualified. |
| Verifier state | PARTIALLY_REPRESENTABLE | Bounded records, enums, arrays, and vectors are supported; the full verifier pipeline remains Python. |
| Emitter/output state | PARTIALLY_REPRESENTABLE | Owned text/bytes and composite records exist; a complete generic S3 emitter is absent. |
| Whole-program compiler context | BLOCKED | The reference compiler remains Python and no S3 composition root implements the complete compiler pipeline. |

## Self-host boundary

`NEXT_SELFHOST_REPRESENTABILITY_BLOCKER=generic text-keyed associative lookup`

The current collection surface can hold arena entries and stable integer IDs,
but generic map support remains the closed `map<i64, i64>` family. Bounded,
deterministic lookup for text or compiler-defined keys is the next
self-host representability increment. It is intentionally not implemented in
this branch.

`SELFHOST_STATUS=DEFERRED_RESEARCH_FRONTIER`
`REFERENCE_COMPILER=PYTHON`
`SELFHOST_REENTRY_AUTHORIZED=NO`
`STAGE1_V4=NOT_AUTHORIZED`

## Final status

`GENERIC_COMPOSITE_VECTOR_HOSTED=YES`
`GENERIC_COMPOSITE_VECTOR_NATIVE_X86_64=YES`
`HOSTED_NATIVE_DIFFERENTIAL=PASS`
`SOAK=PASS`
`NO_UNRESOLVED_CODE_REGRESSION=YES`
`READY_FOR_MAIN_MERGE=YES_WITH_CI_INFRASTRUCTURE_DEBT`

PR #297 remains unmerged and should not be merged automatically. The PR is
marked ready for review. No generic map,
Stage1 V4, release, tag, PyPI, or shutdown action is part of this increment.

`PR_297_STATE=OPEN`
`PR_297_HEAD=0c8e669ad00e140302aec3eb6c0d97e70d0775f9`
`PR_297_DRAFT=NO`
`PR_297_MERGED=NO`
`SHUTDOWN_SCHEDULED=NO`
`SHUTDOWN_EXECUTED=NO`

`NEXT_HARD_GATE=EXPLICIT_USER_AUTHORIZATION_TO_MERGE_PR_297_INTO_MAIN`
