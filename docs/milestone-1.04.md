# Milestone 1.04 - Fixed-Capacity Static Text Foundation

Status: Complete

Milestone 1.04 consolidates the existing static text infrastructure into a
fixed-capacity text value contract and extends record composition so static text
can participate as a scalar leaf. It does not add heap allocation, mutable text
buffers, garbage collection, runtime formatting, public pointers, aggregate
returns, new public IR version, new S3 Assembly version, or a native ABI change.

## Audit Result

S3 already had a typed `string` value model before this milestone:

- lexer/parser build `StringLiteral` expressions;
- semantic analysis tracks `TypeName.STRING`;
- `SemanticModel.static_text_of(...)` records compile-time text results;
- `StaticStringTable` deduplicates decoded static text values;
- IR has `IRType.STRING`, `IRStaticString`, and `CONST_STR`;
- S3 Assembly has `.data`, `string` registers/memory, and `TCONST_STR`;
- the emulator stores string handles as scalar values;
- the native x86-64 backend emits `.rodata` labels and passes private pointers
  through the existing scalar machine path;
- `main -> string` remains rejected so no public process result exposes a
  pointer-like value.

Existing operations were also already compile-time-only:

- literal decoding with LF newline normalization;
- literal-only and immutable-binding concatenation;
- `len(text)`;
- equality and inequality;
- indexing by compile-time index;
- slicing by compile-time bounds;
- `contains`, `starts_with`, `ends_with`, and `find`;
- `upper`, `lower`, `trim`, `repeat`, and `replace`;
- propagation through immutable bindings and match-expression constants.

The real missing composition point was record layout: records still rejected
`string` fields even though `string` was already a scalar IR/Assembly value.

## Representation

A S3 `string` is a fixed-capacity static text value. Its content is known at
compile time and stored in the static string table. The capacity is the exact
UTF-8 byte length of the decoded text value. Native emission uses an internal
NUL-terminated `.asciz` representation for ELF interoperability, but the NUL
terminator is not part of the S3 source value, `len(text)`, indexing bounds, or
semantic capacity.

The runtime value is a scalar handle to immutable static storage:

- hosted emulator: static string id/value handle;
- IR/Assembly: `string` register or memory slot;
- native x86-64: private pointer to `.rodata`.

S3 code cannot observe, forge, compare numerically, or do arithmetic on that
handle. There is no heap, dynamic allocation, text mutation, ownership,
deallocation, or garbage collection.

## Operations

The following operations are supported when their text operands are compile-time
static text expressions:

- `len(text) -> tryte`;
- `text[index] -> string` for a compile-time non-negative index inside bounds;
- `text[start:end] -> string` for compile-time non-negative bounds inside
  bounds and `start <= end`;
- `==` and `!=` returning `trit`;
- `contains(text, fragment) -> trit`;
- `starts_with(text, prefix) -> trit`;
- `ends_with(text, suffix) -> trit`;
- `find(text, fragment) -> tryte`;
- `upper`, `lower`, `trim`, `repeat`, and `replace`;
- copy through variables, parameters, and memory slots;
- record fields and nested record fields;
- imported record fields and multi-module calls.

Operations that require runtime-dependent text contents remain rejected. This
includes indexing, slicing, queries, equality, transforms, or `len(...)` over a
mutable binding, parameter, or non-static function result whose value is not
known to semantic analysis.

## Record Layout

`string` participates in `SemanticModel.record_leaves()` as a scalar leaf. It is
ordered exactly like `trit`, `tryte`, enum discriminants, and nested record
leaves:

- depth-first;
- declaration order;
- nominal identity preserved;
- source-order independent;
- no public offsets or alignment metadata.

Record parameters may therefore include string leaves in their scalarized
internal ABI. Local records, nested records, imported records, qualified
constructors, copies, member chains, O0/O1 lowering, emulator execution, and
native harness coverage all use the same scalar handle path.

## Return Contract

The public return convention remains scalar. A `string` return from helper
functions uses the existing scalar return path. `main -> string` remains
rejected. Records containing exactly one string leaf may use the existing
single-leaf record return rule; records containing multiple leaves remain
rejected until an aggregate-return ABI exists.

## Explicitly Unsupported

- runtime string construction from non-static data;
- mutable text buffers;
- heap allocation;
- garbage collection;
- interpolation or formatting;
- conversion between `string` and numeric handles;
- arrays of string;
- arrays of records;
- aggregate returns;
- public pointer exposure;
- new public IR or Assembly versions.
