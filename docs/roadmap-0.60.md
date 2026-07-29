# Roadmap S3 0.60 - Compile-Time Numeric Constant Pack

## Status

Implementation complete locally; Draft PR validation pending.

## Objective

Milestone 0.60 extends the compile-time model from static text to immutable
scalar constants. It adds propagation for immutable `tryte` and `trit` bindings,
constant folding for the numeric and comparison operators already supported by
S3, and compile-time `tryte` expressions as static text indices and slice
bounds.

No new language syntax or runtime operation is introduced.

## Motivation

The text milestones 0.53 through 0.59 made fixed text usable at compile time.
The next practical step is allowing scalar results from `len`, `find`, query
builtins, and existing numeric expressions to feed later static text operations:

```s3
position: tryte = find("hello", "ll")
letter: string = "hello"[position]
```

## Architecture

Semantic analysis remains the source of truth. It records scalar constants by
expression identity in `SemanticModel.constant_value_of(...)`, while expression
types continue to distinguish `tryte`, `trit`, and `string`.

Immutable scalar bindings store their constant value on the resolved binding.
Identifier expressions receive constants from that binding, so lexical scopes
and shadowing follow the existing resolver. Mutable bindings and parameters do
not propagate constants.

## Constant Model

The representation is typed by combining:

- the existing semantic expression type;
- the scalar value in `SemanticModel.constant_value_of(...)`;
- the static text value in `SemanticModel.static_text_of(...)`.

This prevents using a `trit` constant as a `tryte` index and keeps `tryte -1`
distinct from `trit -1` through the semantic type table.

## Tryte

Immutable `tryte` declarations propagate constants from literals, other
immutable constants, `len(...)`, `find(...)`, and supported numeric expressions.

All results are validated against the existing `tryte` range `[-364, 364]`.
Overflow is rejected during semantic analysis and does not reach lowering.

## Trit

Immutable `trit` declarations propagate constants from literals, static text
query builtins, scalar comparisons, static text equality, and other immutable
`trit` constants.

The only valid values remain `-1`, `0`, and `1`. No boolean type is introduced.

## Operators

0.60 folds only operators that already exist in the language:

- unary `-` and `~`;
- binary `+` and `-`;
- tritwise `&` and `|`;
- `<=>`;
- `==`, `!=`, `<`, `<=`, `>`, `>=`.

There is no multiplication, division, or remainder operator in the current AST
or IR, so none is added. Division by zero is therefore not applicable in this
milestone.

Subtraction follows the existing architecture: addition of the inverted right
operand.

## Comparisons

Constant scalar comparisons fold to `trit` constants. Equality and relational
operators use the existing convention: true is `-1`, false is `0`. `<=>` returns
`-1`, `0`, or `1`.

## Text Integration

`len(...)` and `find(...)` results propagate through immutable `tryte`
bindings. Query builtins returning `trit` propagate through immutable `trit`
bindings.

Static text indexing and slicing accept compile-time `tryte` expressions as
indices and bounds. Bounds are still checked semantically:

```text
0 <= index < len(text)
0 <= start <= end <= len(text)
```

Runtime string indices and runtime slicing remain unsupported.

## Lowering

Lowering queries the semantic model for scalar constants and emits `CONST`
directly. It does not re-evaluate arithmetic, comparisons, bindings, `len`,
`find`, query builtins, indices, bounds, overflow, or text slicing rules.

Materialized strings continue to use the existing static string path. Arrays
continue to use the existing `LOAD` and `STORE` paths.

## Arrays

Array behavior is preserved. Runtime array indices remain valid where they were
already valid. Constant scalar support does not introduce constant arrays,
array evaluation, or array slicing.

## Scopes, Future References, And Cycles

Constants use the existing scope stack. A shadowing declaration creates a new
binding and references resolve to the innermost visible binding.

Bindings are inserted after their initializer is analyzed, so future references
and direct self-reference remain invalid under the current language policy.
No fixpoint solver or interprocedural constant pass is introduced.

## Diagnostics

The milestone reuses existing semantic diagnostics for type mismatches,
unsupported string operations, unresolved names, and range errors. Overflow
uses the existing ternary range messages from the ternary reference model.

No public diagnostic code is added.

## Excluded Scope

0.60 does not add mutable binding propagation, user function execution,
compile-time loops, interprocedural propagation, constant arrays, runtime
strings, runtime string indexing, runtime slicing, heap allocation, garbage
collection, runtime helpers, new opcodes, new Assembly instructions, ABI
changes, backend changes, emulator changes, FFI, libc, public pointers, or
metaprogramming.

## Test Strategy

Coverage includes immutable `tryte` and `trit` propagation, arithmetic,
comparisons, overflow, static text indexing and slicing with constant
expressions, `len`, `find`, query builtins, scopes, future references,
lowering, execution, contracts, arrays, and regressions for 0.53 through 0.59.

## Future Work

Future milestones may consolidate text and scalar constants into a unified
evaluator, add static text transformations, conditional folding, module
constants, aggregate constants, formatting, or interpolation. None of those are
part of 0.60.
