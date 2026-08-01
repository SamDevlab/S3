# Milestone 1.00 - Records and Enums

## Goal

Add the minimal composite type foundation needed for larger S3 programs while
preserving the existing IR, S3 Assembly, native ABI surface, CLI, goldens,
baselines, and public version.

## Delivered

- Nominal `record` declarations with named fields in declaration order.
- Nominal closed `enum` declarations with deterministic `tryte` discriminants
  starting at `0`.
- Record construction with named fields and deterministic field scalarization.
- Field access for local record bindings, record literals, and single-field
  record-return calls.
- Enum construction through qualified `Enum.Variant` syntax.
- Enum `==` and `!=` with nominal type checking.
- Exhaustive `match` over enum selectors, including fallback arms.
- Stable diagnostics for duplicate types, duplicate fields, missing fields,
  unknown fields, duplicate variants, unknown variants, duplicate match arms,
  and non-exhaustive enum matches.
- Record parameters expanded into scalar IR parameters in declared field order.
- Single-field record returns lowered through the existing scalar result
  register.
- Multi-field record returns rejected until an aggregate-return ABI is
  specified.
- Multi-file compilation preserves module-local record and enum names by
  rewriting non-entry module type names to deterministic internal identifiers.
- Native x86-64 coverage was added for record parameters, single-field record
  returns, enum matching, and composite types inside imported modules.

## Layout

Records are scalarized in declaration order. Fields may be `trit`, `tryte`, or
closed enum values. Arrays, `string`, direct nested records, and indirect record
cycles remain outside this milestone. No nested aggregate layout or ABI was
defined.

Enums lower to existing `tryte` registers. The first variant has discriminant
`0`, the second `1`, and so on. The implementation rejects enum declarations
whose non-negative discriminants would exceed the current `tryte` range.

No new IR opcode or S3 Assembly opcode was introduced.

## Non-goals

- no classes;
- no methods;
- no inheritance;
- no traits or interfaces;
- no generics;
- no reflection;
- no enum payloads;
- no heap allocation;
- no open or dynamically extended enum layouts;
- no public format version bump;
- no public linker format.

## Validation

Focused validation covers:

- parser support for record and enum declarations;
- record construction, field access, parameter flattening, and single-field
  returns;
- enum construction, equality, inequality, and exhaustive match;
- duplicate, missing, and unknown record field diagnostics;
- duplicate and unknown enum variant diagnostics;
- duplicate and non-exhaustive enum match diagnostics;
- O0/O1 hosted execution for records and enums;
- multi-file compilation with module-local composite type names;
- native x86-64 collection for composite type programs.

Milestone 1.02-A later aligned the public composition contract with this
delivered behavior without adding nested records or changing ABI.
