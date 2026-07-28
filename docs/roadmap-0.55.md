# Roadmap S3 0.55 - Compile-Time Static Text Length

## Status

Implementation in progress.

## Objective

Milestone 0.55 extends the existing `len(...)` expression so it can accept
compile-time static text expressions in addition to static arrays.

The operation remains compile-time only. It does not introduce dynamic text
length, runtime string traversal, heap allocation, garbage collection, ABI
changes, FFI, libc integration, public pointers, new IR opcodes, or new
Assembly instructions.

## Motivation

S3 already supports typed static text values and literal-only static text
concatenation. Compiler migration work also needs small numeric facts about
fixed text fragments, such as the length of `"TRET "` or `"TRET " + "r1"`.

The useful next step is to reuse `len(...)` for text that the compiler can
fully evaluate before IR generation:

```s3
size: tryte = len("TRET " + "r1")
```

This should compile as an ordinary numeric constant.

## Syntax

No new syntax is introduced.

0.55 reuses the existing `len(expression)` form. Static array behavior is
preserved.

## Semantics

`len(...)` accepts:

- a static array expression supported by the existing language;
- a compile-time static text expression accepted by the 0.54 text model.

A compile-time static text expression is formed only from `StringLiteral` and
`BinaryExpression(BinaryOperator.ADD, left, right)` where both sides are also
compile-time static text expressions.

The result type is `tryte`, matching the existing array `len(...)` result.

## Length Unit

Static text is decoded with the existing static text rules before measuring:

1. supported escapes are decoded;
2. newlines are normalized to LF;
3. literal-only concatenation is evaluated in AST order;
4. the length is the number of decoded logical text units in the resulting
   source-language text value.

UTF-8 byte length remains available in static text metadata, but `len(...)`
does not measure UTF-8 bytes.

Examples:

```s3
len("")             # 0
len("abc")          # 3
len("\n")           # 1
len("\"")           # 1
len("a" + "b")      # 2
len(("a" + "b") + "c") # 3
```

## Architecture

Semantic analysis validates the accepted expression shape and assigns the
existing `tryte` result type.

Lowering evaluates static text using the 0.54 evaluator, computes the decoded
logical length, and emits the existing numeric `CONST` form.

The static string table does not intern text that appears only to compute
`len(...)`.

## Scope

Included:

- literal static text;
- literal-only static text concatenation;
- grouping through the existing expression tree;
- empty text;
- supported escapes;
- Unicode according to the existing decoded text representation;
- use in bindings, returns, and numeric expressions where `tryte` values are
  already valid.

Excluded:

- identifiers and bindings as text constants;
- parameters;
- calls;
- runtime text values;
- dynamic text length;
- string indexing;
- string comparison;
- formatting;
- interpolation;
- heap allocation;
- garbage collection;
- runtime helpers;
- ABI changes;
- new IR opcodes or Assembly instructions.

## Diagnostics

Invalid `len(...)` operands should use existing semantic diagnostics where
possible. The user-facing message should explain that `len(...)` accepts static
arrays or compile-time static text expressions.

Text lengths that do not fit the existing `tryte` result type are rejected in
semantic analysis.

## Lowering

For static text:

1. evaluate the text expression at compile time;
2. compute the decoded logical length;
3. emit a numeric `CONST`;
4. avoid `CONST_STR` and static string table entries when the text is used only
   for length;
5. leave no concat operation for IR, optimizer, Assembly, emulator, or backend.

## Test Strategy

Coverage should include:

- regression tests for static array `len(...)`;
- semantic acceptance of static text literals and literal-only concatenation;
- semantic rejection of runtime-dependent text and unsupported operands;
- lowering to a numeric constant without `CONST_STR`;
- empty text, escapes, and Unicode;
- hosted execution of `len(...)` in returns and numeric expressions;
- contract checks confirming that no runtime, ABI, opcode, heap, or GC surface
  was introduced.

## Future Work

Future milestones may specify dynamic text values, runtime string length,
binding constant propagation, formatting, interpolation, comparison, indexing,
or richer text libraries. None of those features are part of 0.55.
