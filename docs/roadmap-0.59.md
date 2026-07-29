# Roadmap S3 0.59 - Compile-Time Static Text Query And Slice Pack

## Status

Implementation complete locally; Draft PR validation pending.

## Objective

Milestone 0.59 adds a compile-time-only static text query pack:

- `text[start:end]` static slicing;
- `contains(text, fragment) -> trit`;
- `starts_with(text, prefix) -> trit`;
- `ends_with(text, suffix) -> trit`;
- `find(text, fragment) -> tryte`.

No runtime text operation is introduced.

## Motivation

Milestones 0.53 through 0.58 established typed static strings,
compile-time concatenation, length, equality, immutable binding propagation,
and literal indexing. This milestone makes fixed text more useful for
self-hosting checks and renderer construction while preserving the static-only
contract.

## Slicing

`text[start:end]` returns a `string` containing the decoded logical text in the
semi-open interval `[start, end)`.

Both bounds are mandatory. Bounds must be integer literals, non-negative,
ordered as `start <= end`, and satisfy `end <= len(text)`.

The following are outside scope:

- omitted bounds;
- step syntax;
- negative indices;
- dynamic bounds;
- numeric binding propagation;
- array slicing;
- Python-like clamping.

## Unicode Unit

All slicing and query operations use the decoded logical text representation
already used by the static text evaluator. The unit is the host string code
point.

The milestone does not index or search UTF-8 bytes, source-token bytes, raw
escape units, static table offsets, handles, pointers, or grapheme clusters. No
NFC or NFD normalization is added.

## Query Builtins

`contains(text, fragment)` returns `-1` when `fragment` is contained in `text`
and `0` otherwise. The empty fragment is contained in every text, including
empty text.

`starts_with(text, prefix)` returns `-1` when `text` starts with `prefix` and
`0` otherwise. The empty prefix matches.

`ends_with(text, suffix)` returns `-1` when `text` ends with `suffix` and `0`
otherwise. The empty suffix matches.

`find(text, fragment)` returns the first code-point index of `fragment`, `0`
for the empty fragment, and `-1` when not found. The result must fit the
current `tryte` range.

All arguments must be compile-time static text expressions.

## SemanticModel

Semantic analysis remains the source of truth.

`SliceExpression` results are recorded through `SemanticModel.static_text_of`.
Query builtin results are recorded as scalar constants in the semantic model,
using the same expression identity approach as static text values.

The milestone does not add general numeric constant propagation. A `tryte`
binding initialized by `find(...)` is not a compile-time index source for
string indexing or slicing.

## Evaluator

Static text slicing reuses the existing static text evaluator for decoding,
newline handling, concatenation, immutable binding propagation, and indexed
text. Query builtins evaluate only after both operands are resolved by that
same static text path.

No duplicate decoder or runtime lookup is added.

## Lowering

Lowering trusts the semantic model.

Materialized slices emit the existing static string path with `CONST_STR` for
the final sliced value only. Slices used only by `len(...)`, equality, or query
builtins do not require static string table entries.

Query builtins lower directly to scalar `CONST` instructions:

- `contains`, `starts_with`, and `ends_with` emit `trit`;
- `find` emits `tryte`.

No call, loop, branch, textual compare, runtime helper, opcode, Assembly
instruction, ABI change, emulator change, or backend change is introduced.

## Interning

The static string collector avoids interning text used only as input to static
queries. A materialized slice interns only the final sliced value.

Bindings that are real string values keep the existing materialization
behavior. No general dead-code elimination is added.

## Arrays

Array indexing and assignment remain unchanged:

- `array[index]` remains valid;
- runtime indices for arrays remain valid where already supported;
- `LOAD` and `STORE` behavior is preserved;
- array slicing is rejected.

## Diagnostics

The implementation reuses existing semantic diagnostics for unsupported string
operations, invalid argument types, and type mismatches. Parser diagnostics
reject omitted slice bounds and step syntax before semantic analysis.

No public diagnostic code is added.

## Test Strategy

Coverage includes parser, semantic, lowering, execution, contracts, static
string collection, interning, arrays, prior static text milestones, compiler
paths, diagnostics, and renderer contracts.

## Excluded Scope

The milestone does not add runtime slicing, runtime search, dynamic bounds,
dynamic strings, array slicing, heap allocation, garbage collection, runtime
helpers, new opcodes, new Assembly instructions, ABI changes, emulator changes,
backend changes, FFI, libc, public pointers, grapheme clusters, or general
numeric constant propagation.

## Future Work

Future milestones may specify numeric constant propagation for static query
results, dynamic strings, runtime text operations, richer compile-time
evaluation, slicing variants, grapheme clusters, formatting, interpolation, or
lexicographic ordering. None of those are part of 0.59.
