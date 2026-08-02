# Milestone 1.07 - Unified Fixed Value Layouts

Status: In progress - architecture checkpoint for the aggregate-results campaign

Milestone 1.07 defines one semantic contract for every fixed-size value that can
be scalarized by the current compiler. The goal is to make records, payload
enums, scalar nominal values, and fixed static text handles describe their shape
through the same semantic model before aggregate function results are enabled.

This milestone does not change source syntax, IR JSON, S3 Assembly, the native
ABI, goldens, package version, or runtime behavior.

## Problem

The compiler already has enough fixed layout facts to pass records, nested
records, imported records, fixed static text leaves, and payload enum values
through local values and parameters. Those facts are exposed through several
separate queries:

- `SemanticModel.record_leaves()`;
- `SemanticModel.record_leaf_count()`;
- `SemanticModel.enum_layout()`;
- `SemanticModel.enum_payload_leaves()`;
- `SemanticModel.enum_cell_count()`;
- return validation helpers inside semantic analysis;
- lowering-specific binding and scalarization paths.

These APIs agree today because they share local helper code, but they still make
callers choose record-specific or enum-specific concepts. Aggregate returns need
one source of truth that can answer "what fixed cells does this declared type
have?" and "is this declared type returnable under the current ABI?" without
duplicating layout rules in lowering.

## Value Layout Contract

The canonical model is a semantic, target-independent fixed value layout. It
describes logical cells only. It must not expose physical offsets, stack slots,
register allocation, alignment, padding, native ABI classes, or S3 Assembly
serialization details.

A fixed value layout has:

- a declared source type;
- a layout kind;
- an ordered tuple of logical cells;
- nominal dependencies that affect layout validity;
- a return classification derived from the same cells and language rules.

A logical cell has:

- a stable logical path;
- one scalar storage type;
- a source location for diagnostics.

Logical paths are source-level paths, not physical addresses. Scalar values use
the empty path. Record cells use declared field names recursively. Enum payload
layouts use a tag cell followed by payload slot cells. Fixed static text values
use one scalar handle cell and retain their static text contract separately.

## Layout Kinds

The initial fixed layout kinds are:

| Kind | Cells | Notes |
| --- | --- | --- |
| Scalar | one cell | `trit` and `tryte`; source-level scalar return compatible. |
| Fixed static text | one `string` handle cell | Compile-time-known text handle; not a general runtime string. |
| Record | depth-first declared leaves | Includes scalar, fixed text, enum, and acyclic nested record fields. |
| Enum | tag-first fixed cells | Cell 0 is the `tryte` discriminant; payload cells follow canonical slot types. |

Arrays remain outside this fixed value layout contract. Heap values, dynamic
text, pointers, recursive layouts, and open-ended aggregate storage also remain
outside the contract.

## Return Classification

Return classification is derived from the same semantic layout rather than from
lowering-specific width checks.

The initial classes are:

- scalar-return-compatible: source-level scalar types and nominal values whose
  current language contract explicitly allows one scalar return cell;
- aggregate-fixed-layout: fixed layouts that have multiple cells and require a
  future aggregate return convention;
- not-returnable: types that are fixed internally but not allowed as direct
  function returns by current language rules, including static text values and
  unsupported array forms.

This preserves the current behavior:

- arrays cannot be returned;
- `main -> string` remains rejected;
- multi-leaf records remain rejected;
- multi-cell payload enums remain rejected;
- no hidden return pointer, multi-register return, stack return area, packing
  rule, heap allocation, or ABI change is introduced.

## Compatibility Queries

Existing public semantic queries remain compatibility wrappers during this
campaign:

- `record_leaves(name)` is derived from the record value layout;
- `record_leaf_count(name)` is derived from `record_leaves(name)`;
- `enum_layout(name)` is derived from the enum value layout and preserves the
  ADR-0021 tag-plus-payload shape;
- `enum_payload_leaves(name, variant)` is derived from the enum layout;
- `enum_cell_count(name)` is derived from the enum layout.

New implementation work should consume the canonical fixed value layout first
when a caller needs a type-wide answer. Lowering may continue to use existing
wrappers only when the operation is inherently record-specific or enum-specific.

## Invariants

- Layout is deterministic and follows source declaration order.
- Nominal type identity is the defining module plus type name.
- Record flattening is depth-first and acyclic.
- Enum layouts are fixed-width by enum type, tag-first, and use canonical slot
  types.
- Inactive enum slots are initialized deterministically and are not observable
  as source payload fields.
- Fixed text remains compile-time-known and is represented as one scalar handle
  cell where field layout needs a scalar leaf.
- The semantic model owns layout decisions; lowering consumes them.
- No target backend may invent an independent layout algorithm.

## 1.07 Deliverables

- Add the canonical fixed value layout data model to semantic analysis.
- Route existing record and enum layout queries through that model.
- Route semantic return validation through the return classification.
- Keep behavior-compatible lowering by consuming the same semantic facts.
- Add focused tests proving wrapper compatibility and return classification.

## Non-Goals

- No aggregate function result implementation.
- No change to the scalar return ABI.
- No S3 Assembly or IR version bump.
- No native ABI change.
- No arrays in records or function signatures.
- No dynamic strings, heap allocation, exceptions, generics, or implicit error
  propagation.
