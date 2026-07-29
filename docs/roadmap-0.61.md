# Roadmap S3 0.61 - Unified Constant Evaluator And Static Text Transformation Pack

## Status

Planned. This milestone specifies the next compile-time layer after 0.60.

## Objective

Milestone 0.61 consolidates static text constants and scalar constants behind a
single semantic constant evaluator, then adds a small compile-time-only static
text transformation pack.

The intended transformations are:

- `upper(text) -> string`;
- `lower(text) -> string`;
- `trim(text) -> string`;
- `repeat(text, count) -> string`;
- `replace(text, old, new) -> string`.

No runtime string operation is introduced.

## Motivation

Milestones 0.53 through 0.60 established typed static strings, compile-time
concatenation, length, equality, immutable binding propagation, static text
indexing, slicing, queries, immutable scalar constants, and numeric expression
folding.

That model is now useful but split across two semantic tables:

- `SemanticModel.static_text_of(...)` for text;
- `SemanticModel.constant_value_of(...)` plus `type_of(...)` for scalars.

0.61 should make those paths easier to reason about before the language grows
conditional folding, module constants, aggregate constants, formatting, or
interpolation.

## Architecture

Semantic analysis remains the source of truth. The evaluator should be an
internal semantic component, not a lowering or optimizer rule.

Conceptually, the evaluator owns a typed constant value model:

```text
ConstantValue
  StaticText(value: str)
  Tryte(value: int)
  Trit(value: int)
```

The project does not need to expose these names publicly if a different local
shape fits better. The important contract is that every constant result is
typed and validated before lowering sees it.

`SemanticModel.static_text_of(...)` and `SemanticModel.constant_value_of(...)`
may remain as compatibility accessors. If the internal representation changes,
those public semantic queries should still answer the existing callers.

## Unified Evaluation

The evaluator should handle the compile-time expressions already supported by
0.60:

- string literals;
- immutable static text identifiers;
- string concatenation;
- static text indexing and slicing;
- `len(...)`;
- static text equality and inequality;
- `contains(...)`, `starts_with(...)`, `ends_with(...)`, and `find(...)`;
- immutable `tryte` and `trit` identifiers;
- integer literals;
- unary `-` and `~`;
- binary `+`, `-`, `&`, `|`;
- `<=>`;
- scalar equality and relational comparisons.

The evaluator should not evaluate arbitrary user functions, loops, recursion,
mutable bindings, parameters, arrays, or runtime-dependent expressions.

## Static Text Transformations

All 0.61 transformations are compile-time-only builtins. Their arguments must
be compile-time constants.

`upper(text)` and `lower(text)` operate on the decoded static text value. Their
Unicode policy must be explicit before implementation. The conservative default
is host Unicode case mapping for decoded code points, matching the existing
host-string static text model.

`trim(text)` removes leading and trailing ASCII whitespace unless the milestone
explicitly adopts a broader Unicode whitespace policy. The policy must be
covered by tests.

`repeat(text, count)` repeats text `count` times. `count` must be a compile-time
`tryte` value. Negative counts are rejected semantically. The resulting text
length must fit the existing static text and tryte-related limits used by
callers such as `len(...)`.

`replace(text, old, new)` performs a compile-time replacement on decoded static
text. The empty `old` fragment is rejected semantically to avoid surprising
insertion behavior.

## Typing

Transformation results have type `string` and are static text constants.

`repeat` requires a `tryte` count. It must not accept a `trit` count by sharing
only the scalar integer value. This keeps the 0.60 typed-constant contract
intact.

No boolean type is introduced. Query builtins continue to return `trit`.

## Lowering

Lowering must not evaluate transformations. It should ask the semantic model
for the final constant result.

Materialized transformation results use the existing static string table and
`CONST_STR` path. Transformation results used only by `len`, equality, query
builtins, indexing, slicing, or another transformation do not require static
string table entries unless current materialization rules already require one.

No call, branch, loop, runtime helper, opcode, Assembly instruction, ABI
change, backend change, emulator change, FFI, libc, heap allocation, garbage
collection, or public pointer is added.

## Diagnostics

The implementation should reuse existing semantic diagnostics for type
mismatches, invalid argument types, unsupported string operations, and range
errors.

New public diagnostic codes should be avoided unless an existing code cannot
represent a required user-facing error.

Required diagnostic cases include:

- non-static text transformation argument;
- non-`tryte` repeat count;
- negative repeat count;
- repeat result too large;
- `replace` with an empty search fragment;
- mutable binding used where a static transformation input is required;
- parameter or runtime call used where a static transformation input is
  required.

## Arrays

Array behavior is preserved. 0.61 does not add constant arrays, array
evaluation, array slicing, array transforms, or array string conversion.

Runtime array indexing remains valid where it was already valid.

## Scopes, Future References, And Cycles

Constants continue to use the existing lexical binding policy. Shadowing should
resolve through the existing binding object, not by textual name alone.

Future references and direct self-reference remain invalid under the current
declaration policy. No fixpoint solver is introduced.

## Excluded Scope

0.61 does not add runtime strings, runtime text transforms, dynamic string
indexing, runtime slicing, user-defined const functions, compile-time loops,
compile-time recursion, interprocedural propagation, module constants,
conditional folding, constant arrays, records, enums, structs, formatting,
interpolation, heap allocation, garbage collection, runtime helpers, new
opcodes, new Assembly instructions, ABI changes, backend changes, emulator
changes, FFI, libc, public pointers, grapheme clusters, normalization forms, or
locale-sensitive text behavior.

## Test Strategy

Coverage should include:

- public semantic accessors after the evaluator consolidation;
- all pre-0.61 constant features from 0.53 through 0.60;
- `upper`, `lower`, `trim`, `repeat`, and `replace`;
- transformation chaining;
- transformations feeding `len`, equality, query builtins, indexing, slicing,
  and scalar propagation;
- no interning for transformed text used only as an intermediate;
- materialization for transformed text assigned to a `string` value;
- diagnostics for runtime, mutable, parameter, wrong-type, and invalid-bound
  inputs;
- lowering proving no runtime calls or helpers are emitted;
- execution tests for programs returning scalar results derived from
  transformations;
- renderer and static string contracts.

## Future Work

0.62 may add compile-time conditional and control-flow folding. 0.63 may add
module constants. 0.64 may add static arrays and aggregate constants. 0.65 may
add compile-time formatting and interpolation.

Those milestones should build on the unified evaluator rather than adding new
parallel constant paths.
