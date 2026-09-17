# S3 1.2 Composite Vector Representability

Date: 2026-09-17
Base main: `1e978b0d988f999d31ad15bdd6889393043e906a`
Implementation HEAD: `03945328de0315cb6f24624f2903ed5b21babcae`
Status: `IMPLEMENTED_HOSTED_FOCUSED_VERIFIED`

This report records the generic composite-vector increment and its boundary.
It does not claim a self-hosted compiler, Stage1 V4, Stage2, or a native
composite-vector runtime.

The requested historical inputs were inspected. `docs/milestone-1.52.md` is
not present on the base tree; the existing M1.51/M1.53-M1.60 reports and the
M1.51 composite-owned-values specification were used without recreating that
missing document.

## Implemented contract

`vector<T>` now has a compile-time `VectorType` for eligible non-scalar
elements. The existing scalar adapters remain unchanged for `tryte`, `i64`,
and `f64`. Composite elements use one shared deterministic type-key helper,
the existing semantic fixed-value layout, and a monomorphized runtime callee
whose cell codes are derived from that layout.

Supported hosted compositions proven by focused programs:

- records, including nested records;
- enums and parametric enums;
- parametric records after specialization;
- fixed arrays nested in a vector element;
- records containing owned `text` leaves;
- multiple unrelated nominal element types through the same generic path.

The vector operations covered are construction, length, capacity, push,
indexed read, replacement, clone, slice, move, and drop. Composite reads and
returns use the existing multi-cell IR result contract. A one-cell composite
result is kept scalar at the emulator boundary; wider results remain ordered
cell tuples.

## Eligibility and safety

Eligibility is checked during semantic analysis and uses the existing
`fixed_value_layout` metadata. The lowerer does not reconstruct a competing
layout. Recursive records, nested dynamic collections, references, slices,
type parameters, and empty layouts are rejected before lowering. The current
compatibility rule also continues to reject `vector<string>`.

The runtime representation is bounded by explicit capacity and a fixed cell
stride. It validates each cell with the established `trit`, `tryte`, `i64`, and
`f64` validators. Borrow conflicts, capacity exhaustion, out-of-bounds access,
move-after-move, and post-drop access are fail-closed. Owned text cells are
deep-cloned through their existing clone operation.

No runtime reflection, GC, raw public pointer, dynamic dispatch, implicit
growth, fixture-name dispatch, or new FFI ABI was introduced.

## Representability matrix

The classifications below describe the evidence available in ordinary S3
today. `REPRESENTABLE_NOW` means the value shape is supported by the current
language/runtime feature; it does not mean the full self-host compiler exists.

| Structure | Classification | Evidence and boundary |
| --- | --- | --- |
| SourceView / bounded source transport | PARTIALLY_REPRESENTABLE | Bounded scalar/text values exist, but no generic source-file transport path was added here. |
| Token | REPRESENTABLE_NOW | `vector<Token>` with owned text and indexed field projection passes at O0/O1. |
| AST/HIR Node | PARTIALLY_REPRESENTABLE | Flat ID-based records and enum payloads are supported; a complete syntax arena model is not present. |
| ScopeId | REPRESENTABLE_NOW | Ordinary bounded `i64` IDs and scalar vectors are supported. |
| Scope | PARTIALLY_REPRESENTABLE | Record storage is possible, but general text-keyed lookup is not available. |
| DeclarationId | REPRESENTABLE_NOW | Ordinary bounded `i64` IDs are supported. |
| Declaration | PARTIALLY_REPRESENTABLE | Composite record storage is supported; the full declaration metadata shape is not qualified. |
| TypeId | REPRESENTABLE_NOW | Ordinary bounded `i64` IDs are supported. |
| TypeInfo | PARTIALLY_REPRESENTABLE | Parametric and enum value shapes are supported, but recursive type metadata and lookup are not complete. |
| FunctionId | REPRESENTABLE_NOW | Ordinary bounded `i64` IDs are supported. |
| StorageId | REPRESENTABLE_NOW | Ordinary bounded `i64` IDs are supported. |
| BlockId | REPRESENTABLE_NOW | Ordinary bounded `i64` IDs are supported. |
| Block | PARTIALLY_REPRESENTABLE | Flat block records with integer relationships are supported; complete CFG arena behavior is not qualified. |
| ValueId | REPRESENTABLE_NOW | Ordinary bounded `i64` IDs are supported. |
| InstructionId | REPRESENTABLE_NOW | Ordinary bounded `i64` IDs are supported. |
| Instruction | PARTIALLY_REPRESENTABLE | Fixed fields and arrays are supported; complete generic instruction metadata is not qualified. |
| Verifier state | PARTIALLY_REPRESENTABLE | Records, enums, arrays, and vectors can carry bounded state, but the full verifier pipeline is not an S3 program. |
| Emitter/output state | PARTIALLY_REPRESENTABLE | Owned text/bytes and composite records exist; a complete generic output emitter is not present. |
| Whole-program compiler context | BLOCKED | The current reference compiler remains Python and no ordinary S3 composition root implements the full compiler pipeline. |

The current matrix records the important distinction between ID storage and
the compiler subsystems that consume those IDs. It is not evidence that the
historical self-hosting experiments have become a new candidate.

## Layout and determinism

Logical element cells follow the established declaration-order traversal for
records, increasing array index order, and the existing enum discriminant and
payload layout. The same semantic layout supplies the runtime cell codes and
the IR CALL signature. Repeated compilation of the fixed-array fixture yields
identical IR dictionaries. Nominal specialization names remain deterministic
and include the existing type-key format.

The hosted emulator is the semantic oracle. O0 and O1 agree for records,
enums, parametric records/enums, owned text, and fixed-array elements. The
feature does not add a native layout implementation. The x86-64 backend
currently rejects a composite-vector CALL at assembly verification because it
has no corresponding native builtin symbol or aggregate-vector ABI/runtime
implementation. This is an explicit native limitation, not a claim of native
success. Compact EA policy is unchanged and therefore cannot be certified for
composite-vector native execution in this increment.

## Self-host gate accounting

| Gate | State | Rationale |
| --- | --- | --- |
| Gate 2, S3 representability matrix | SUPPORTED_BY_EVIDENCE | This document provides the required structure-by-structure matrix and boundaries. |
| Gate 4, composition-root transport | PARTIAL | Bounded value transport is available; the full composition root remains absent. |
| Gate 5, structured syntax representation | PARTIAL | Composite syntax-shaped values are representable, but the complete Stage1 subset is not. |
| Gate 6, semantic arena representation | PARTIAL | ID-bearing records are representable; general scoped lookup is not. |
| Gate 7, IR representation | PARTIAL | Instruction-like records and deterministic cell layouts are representable; full generic IR is not. |
| Gate 8, verifier state | PARTIAL | Existing Python verifier contracts remain authoritative. |
| Gate 9, emitter/output state | PARTIAL | Existing output values are reusable; full S3 emitter composition is absent. |
| Gate 11, bounded complexity | SUPPORTED_BY_EVIDENCE | Vector indexing is bounded by explicit capacity and fixed element width; the remaining compiler-wide complexity budget is not implied. |
| Gate 15, authorization | UNCHANGED | This feature does not authorize a new self-host implementation generation. |

`ANTI_SPECIALIZATION=PASS` for the feature boundary: the focused matrix uses
Pair, Token, State, Box, Maybe, and fixed-array elements without production
branches keyed to those names. The common path is driven by declared layout
and type identity.

## Validation evidence

Windows focused suite: `91 collected`, `90 passed`, `1 skipped`.
Windows full suite: `3383 collected`, `EXIT=0`, no failures reported by the
quiet terminal run. The quiet run did not emit a final skip decomposition, so
the skip count is intentionally not reconstructed here.

Linux hosted focused suite: `PASS` on the exact implementation snapshot,
using the VM's existing Python 3.14.4 venv because Python 3.13.15 was not
available. The Linux recut covered the composite-vector and adjacent generic,
ownership, IR, and verifier tests.

Linux native composite probe: `BLOCKED`. Compilation reached assembly, then
`X8664Backend` failed closed with an `AssemblyVerifierError` for the generated
composite-vector callee because the native builtin/ABI/runtime path does not
exist yet.

`COMPILEALL=PASS` and `DIFF_CHECK=PASS` were run on Windows. No benchmark,
release, tag, or PyPI action was performed.

## Next blocker

`NEXT_SELFHOST_REPRESENTABILITY_BLOCKER=generic text-keyed associative lookup`

The current collection surface can now hold arena entries and stable integer
IDs, but the existing generic map support remains the closed `map<i64, i64>`
family. Ordinary compiler scopes, declarations, and type metadata need a
bounded deterministic lookup structure for text or compiler-defined keys.
That is the next self-host representability increment. The native composite
vector ABI/runtime is an independent product/backend blocker and must be
closed before native composite-vector certification, but it is not silently
counted as a self-host success here.

`SELFHOST_STATUS=DEFERRED_RESEARCH_FRONTIER`
`REFERENCE_COMPILER=PYTHON`
`SELFHOST_REENTRY_AUTHORIZED=NO`
`STAGE1_V4=NOT_AUTHORIZED`
`PUBLIC_ABI_DECISION_REQUIRED=NO`
