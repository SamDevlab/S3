# Roadmap S3 0.56 - Compile-Time Static Text Equality

## Status

Implementation in progress.

## Objective

Milestone 0.56 accepts `==` and `!=` between compile-time static text
expressions. The comparison is resolved during compilation and produces the
same `trit` result convention as existing numeric comparisons.

The milestone does not introduce runtime text comparison, dynamic strings,
heap allocation, garbage collection, ABI changes, FFI, libc integration, public
pointers, new IR opcodes, new Assembly instructions, emulator behavior, or
backend behavior.

## Motivation

S3 can already represent static text values, concatenate literal-only static
text, and compute static text length. Equality over fixed text fragments is the
next small operation needed by compiler migration experiments, diagnostics, and
renderer checks.

Examples:

```s3
same: trit = "abc" == "abc"
different: trit = ("a" + "b") != "ac"
```

Both examples should lower to ordinary numeric constants.

## Syntax

No new syntax is introduced. The milestone reuses existing relational
operators:

- `==`
- `!=`

The parser already gives additive expressions higher precedence than
relational equality, so `"a" + "b" == "ab"` is parsed as
`("a" + "b") == "ab"`.

## Semantics

Accepted operands are compile-time static text expressions from the 0.54
contract:

- `StringLiteral`
- literal-only `BinaryExpression(BinaryOperator.ADD, left, right)`

Both operands must be fully evaluable at compile time. Identifiers, bindings,
parameters, calls, and runtime values do not participate in 0.56 text equality.

The result type is `trit`, matching existing comparisons:

- true is `-1`
- false is `0`

## Equality Definition

Text is decoded with the existing static text rules before comparison:

1. supported escapes are decoded;
2. newlines are normalized to LF;
3. literal-only concatenation is evaluated in AST order;
4. the final decoded logical text values are compared exactly.

The comparison does not use token spelling, raw source bytes, runtime pointers,
or UTF-8 hashes.

## Included Scope

- `"" == ""`
- `"abc" == "abc"`
- `"abc" != "xyz"`
- `"a" + "b" == "ab"`
- `("a" + "b") != ("a" + "c")`
- supported escapes
- Unicode according to the existing decoded logical text representation
- use anywhere existing `trit` comparison results are valid

## Excluded Scope

- string bindings in comparisons
- mutable bindings
- parameters
- function calls
- runtime string comparison
- lexicographic text ordering
- `<`, `<=`, `>`, `>=` over text
- indexing
- formatting
- interpolation
- runtime helpers
- heap allocation
- garbage collection
- public pointers
- FFI
- libc
- IR opcode changes
- Assembly instruction changes
- ABI changes
- emulator or backend runtime behavior

## Architecture

Semantic analysis recognizes static text equality before the generic
relational path rejects string operands. It validates both text expressions,
assigns the existing `trit` result type, and preserves numeric comparison
behavior.

Lowering assumes semantic validation, evaluates both operands with the 0.54
static text evaluator, compares decoded logical values, and emits a numeric
`CONST` of type `trit`.

The static string collector skips text used only in compile-time equality, so
such expressions do not create static table entries or `CONST_STR`.

## Diagnostics

Unsupported string comparison cases reuse the existing unsupported string
operation diagnostic where appropriate. Mixed text/non-text operands continue
to use ordinary type mismatch behavior.

No public diagnostic code is added.

## Test Strategy

Coverage should include:

- semantic acceptance of equality and inequality over literal-only static text;
- semantic rejection of bindings, parameters, calls, and mixed operands;
- result type compatibility with existing `trit` comparisons;
- lowering to a single numeric constant;
- absence of `CONST_STR` and unnecessary static string entries;
- empty text, escapes, Unicode, grouping, and nested concatenation;
- execution through hosted `main -> trit`;
- regression coverage for 0.54 concatenation, 0.55 `len`, and numeric
  comparisons;
- contract checks confirming no runtime, ABI, opcode, Assembly, heap, GC, or
  backend surface is introduced.

## Future Work

Future milestones may specify runtime string equality, binding constant
propagation, lexicographic comparison, text indexing, formatting,
interpolation, or richer string libraries. None of those features are part of
0.56.
