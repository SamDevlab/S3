# Roadmap S3 0.58 - Compile-Time Static Text Indexing

## Status

Implementation complete locally; Draft PR validation pending.

## Objective

Milestone 0.58 adds compile-time indexing for static text expressions using the
existing indexing syntax:

```s3
letter: string = "abc"[1]
```

The result is a `string` containing exactly one logical character from the
decoded static text value.

## Motivation

The static text features from 0.53 through 0.57 allow fixed text to be stored,
concatenated, measured, compared, and propagated through immutable bindings.
Indexing lets fixed fragments be selected without introducing runtime strings
or a character type.

## Syntax And Type

`text[index]` is accepted when `text` is a compile-time static text expression
and `index` is a supported compile-time integer literal.

The result type is always `string`. S3 does not gain a `char`, byte, code point,
handle, pointer, or integer result for text indexing.

## Unicode Unit

Indexing uses the logical code point sequence already produced by static text
decoding. It does not index UTF-8 bytes, source-token bytes, table offsets,
handles, pointers, or escape units.

No NFC/NFD normalization or grapheme cluster segmentation is introduced.
Sequences formed from multiple code points continue to occupy multiple
positions.

## Accepted Indices

This milestone accepts only integer literals, including the parenthesized form
that the AST naturally erases.

Negative literals are rejected. Numeric binding propagation, parameter indices,
runtime indices, and arithmetic index evaluation are intentionally outside
scope for strings.

## Bounds

Semantic analysis validates:

```text
0 <= index < len(text)
```

Out-of-bounds text indices are rejected before lowering, IR, Assembly,
emulation, or native code generation. Python `IndexError` or host exceptions are
not part of the contract.

## Architecture Found

Before 0.58, the parser built `IndexExpression` only for identifier targets,
and the AST stored an `array_name`. Semantic analysis rejected string targets
with the existing unsupported string operation diagnostic, while lowering
treated every index expression as an array load.

0.58 extends `IndexExpression` to store the indexed target expression while
preserving the identifier `array_name` compatibility path for arrays. The parser
keeps indexing at primary/postfix precedence, above concatenation and equality,
and does not introduce slicing or chained indexing syntax.

## SemanticModel

Semantic analysis remains the source of truth. For static text indexing it:

- resolves the target static text using the same static text evaluator used by
  concatenation, length, equality, and immutable binding propagation;
- checks that the index has `tryte` type;
- accepts only a literal integer index for strings;
- validates non-negativity and bounds;
- records the one-code-point result in `SemanticModel.static_text_of(...)`;
- assigns the expression type `string`.

Lowering does not perform binding lookup for static text indexing.

## Evaluator

The static text evaluator was extended with explicit index-expression support.
It reuses the existing decoding, newline normalization, concatenation, and
immutable binding resolution paths. No second string decoder is introduced.

## Lowering

For a valid static text index expression, lowering queries
`SemanticModel.static_text_of(...)` and emits the existing static string value
path only when the result is materialized.

`len("abc"[1])` lowers to `CONST tryte 1`, and `"abc"[1] == "b"` lowers to a
`CONST trit` result. No string index operation, bounds check, helper call,
branch, opcode, Assembly instruction, ABI change, emulator change, or backend
change is added.

## Integration With 0.54 To 0.57

- 0.54 concatenation can use indexed text results.
- 0.55 `len(...)` can measure indexed text at compile time.
- 0.56 equality and inequality can compare indexed text at compile time.
- 0.57 immutable static text bindings can be indexed and can receive indexed
  results.

## Arrays

Array indexing remains separate. Identifier targets whose binding is an array
continue through the existing array index analyzer and lowering path. Runtime
array indices and array `LOAD`/`STORE` behavior are preserved.

String index assignment remains unsupported.

## Interning

Materialized string values intern only the final static text result needed by
the program. Text used only inside static `len(...)` or static equality does not
need a string table entry.

A source binding such as `source: string = "abc"` may still materialize
`"abc"` because it is a real string value.

## Diagnostics

The milestone reuses existing semantic diagnostics:

- unsupported string operation for runtime-dependent or unsupported string
  indexing;
- type mismatch for invalid result assignments or invalid index types;
- existing array diagnostics for array indexing;
- existing immutable assignment diagnostics for attempted string index writes.

No public diagnostic code is added.

## Excluded Scope

The milestone does not add runtime string indexing, dynamic string indices,
numeric constant propagation, slicing, ranges, mutation, a `char` type,
substring search, formatting, interpolation, heap allocation, garbage
collection, runtime helpers, public pointers, FFI, libc integration, new IR
opcodes, new Assembly instructions, ABI changes, emulator behavior, or backend
behavior.

## Test Strategy

Coverage includes:

- parser and precedence for literal, binding, grouped concatenation, `len`, and
  equality;
- semantic success for first, middle, last, binding chains, escapes, newlines,
  Unicode code points, equality, length, concatenation, and shadowing;
- semantic rejection of empty text, out-of-bounds indices, negative indices,
  runtime indices, parameters, calls, mutable text, non-string targets, invalid
  index types, incompatible result types, and string index assignment;
- lowering and interning for materialized values, `len`, equality, and
  concatenation;
- execution through the existing hosted pipeline;
- regressions for arrays and prior static text milestones.

## Risks And Future Work

Future work may specify dynamic strings, numeric constant propagation, broader
compile-time expressions, direct chained text indexing, slicing, grapheme
clusters, formatting, interpolation, lexicographic ordering, or runtime text
operations. None of those are part of 0.58.
