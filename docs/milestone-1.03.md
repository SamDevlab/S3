# Milestone 1.03 - Acyclic Nested Records and Deterministic Composite Layout

Status:
In progress

Milestone 1.03 extends the 1.00 and 1.02 record contracts to allow acyclic
nested record fields. It preserves the existing public IR, S3 Assembly,
diagnostic schema, native ABI, CLI, golden artifacts, baselines, tags, releases,
and package version.

## Architectural Audit

The 1.03-A audit found:

- AST and parser already represent record fields as general declared types, so
  local and module-qualified nominal record field types require no syntax
  change.
- Module rewriting already rewrites field type annotations and qualified record
  constructors to deterministic internal nominal names.
- Semantic analysis currently rejects any record field whose nominal type is not
  an enum with `nested record fields are not supported yet`.
- Record identity is the rewritten nominal type name derived from
  `ModuleId + TypeName`, for example `__s3mod_geometry__type_Point`.
- Lowering currently stores record values as `_LoweredBinding.fields` and
  expands shallow record parameters into scalar IR parameters in declaration
  order.
- Single-field record returns use the existing scalar return path.
- Multi-field record returns are rejected before lowering and again guarded in
  lowering.
- IR, verifier, SSA, optimizer, Assembly, emulator, and native x86-64 backend
  operate on scalar registers and scalar parameters after lowering.

Conclusion:

Nested records for literals, immutable locals, copies, parameters, field access,
member chains, and imported record fields are representable with the existing
scalar IR and Assembly formats when lowering expands all scalar leaves. Multi
leaf returns remain incompatible with the current return convention and must
stay rejected.

## 1.03-B - Initial Architecture Gate

Status:
Passed for non-return nested record contexts.

The implementation may proceed without public format changes for:

- local record fields;
- imported record fields;
- nested and qualified record constructors;
- immutable local bindings;
- copies by value;
- parameters;
- chained member access;
- branch, loop, and match contexts whose observable value is scalar;
- multi-file and source-order deterministic programs.

The implementation must reject before lowering:

- direct and indirect layout cycles;
- unsupported leaf types;
- multi-leaf record returns;
- arrays and strings as record fields;
- recursive layouts that would otherwise cause Python `RecursionError`.

## 1.03-C - Specification

Status:
Complete

Normative decision:

- [ADR-0020](decisions/ADR-0020-acyclic-nested-record-layout.md).

Nested record layout is a logical list of scalar leaves. Flattening is
depth-first and follows declaration order at each record level. It does not
define public offsets, alignment, padding, aggregate objects, hidden pointers,
or physical layout metadata.

Leaf rules:

- `trit` contributes one scalar leaf;
- `tryte` contributes one scalar leaf;
- a closed enum without payload contributes one `tryte` scalar leaf;
- an acyclic nested record contributes its leaves recursively.

Return rule:

- a record with exactly one scalar leaf may use the existing scalar return path;
- a record with more than one scalar leaf is rejected until an aggregate-return
  ABI is specified.

## Planned Units

- 1.03-D - cycle tests first;
- 1.03-E - semantic cycle detection and leaf layout;
- 1.03-F - nested record value semantics;
- 1.03-G - fixed nested record lowering;
- 1.03-H - native coverage;
- 1.03-I - documentation closure.

## Explicitly Unsupported

- recursive record layouts;
- arrays as record fields;
- strings as record fields;
- arrays of records;
- aggregate returns;
- hidden return pointers;
- multi-register returns;
- heap allocation;
- public offsets or alignment metadata;
- structural typing across modules.
