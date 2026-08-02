# ADR-0024 - Bounded Text Processing, Cursors, And Source Spans

Status: Accepted

## Context

S3 `string` is an immutable handle to compile-time-known static text. Its
capacity is the decoded UTF-8 byte count and its content lives in the static
string table. Compile-time operations can inspect it, but runtime S3 code
cannot read code units from a parameter-dependent string handle. That contract
is appropriate for literals and static rendering, but it cannot support an
incremental self-hosted tokenizer or parser.

Milestone 1.12 made fixed `tryte` arrays complete copy-by-value values across
function, record, enum, module, emulator, and native boundaries. Milestone 1.13
uses that canonical layout to define a bounded operational text value without
changing the existing `string` representation, exposing pointers, or adding
dynamic storage.

## Decision

S3 gains a small self-hosting text foundation represented as nominal values
built from existing language features. It is not a new primitive type and does
not change IR or Assembly formats.

The concrete operational text representation is:

```s3
record BoundedText:
    length: tryte
    units: tryte[364]
```

`BoundedText` is one fixed-layout copy-by-value value. `length` is the logical
number of code units and must be in `0..364`. `units` has physical capacity 364.
Cells at indices greater than or equal to `length` are deterministic zero
padding and are not part of the logical text.

The existing `string` type remains the compile-time static text representation.
Python harnesses may encode an accepted static string into `BoundedText` test
data, but no implicit source conversion, hidden runtime conversion, or default
compiler path is introduced.

## Capacity And Index Domain

The fixed capacity is 364 code units. This is one less than the existing
maximum array length of 365 because a cursor must represent every element
position and the end position. A `tryte` can represent `0..364`, so:

- valid element indices are `0..363` when the text is full;
- end-of-input for full text is cursor position `364`;
- logical length is always representable by one `tryte`;
- no two-cell integer or sentinel encoding is needed.

Text longer than 364 code units is rejected before entering the bounded
component. Capacity is static and cannot grow.

## Code Units And Encoding

Each logical cell is one non-negative ASCII code unit stored in a `tryte`.
Accepted code units are:

- horizontal tab: `9`;
- line feed: `10`;
- carriage return: `13`;
- printable ASCII: `32..126`.

Zero is reserved for padding and is invalid inside the logical prefix. Other
control codes and values outside the accepted set are invalid input. Assembly
tokenization normalizes no characters; CR and LF remain distinct code units,
and a later tokenizer may recognize CRLF explicitly.

This decision does not claim UTF-8 decoding, arbitrary UTF-8 byte processing,
Unicode scalar values, grapheme clusters, locale-sensitive classification, or
normalization. Static `string` artifacts may contain broader UTF-8, but only the
accepted ASCII subset can be encoded as `BoundedText` for these self-hosted
components.

## Cursor

The concrete cursor is:

```s3
record TextCursor:
    position: tryte
```

A cursor contains only a scalar index. It does not contain text, capacity,
memory identity, a handle, a pointer, or a reference. Every operation that
needs input receives both `BoundedText` and `TextCursor` explicitly.

For text of logical length `L`:

- positions `0..L-1` identify code units;
- position `L` is the unique end-of-input cursor;
- negative positions or positions greater than `L` are invalid;
- reading at `L` is an explicit end-of-input result, not a bounds trap;
- advancing at `L` is an explicit end-of-input error/result.

## Source Span

The concrete span is:

```s3
record SourceSpan:
    start: tryte
    end: tryte
```

Spans use half-open `[start, end)` coordinates. Start/end is selected instead
of start/length because tokenizer and parser operations naturally retain the
start cursor and finish at a later cursor, while both values remain directly
bounded by the input length.

A span is valid for text length `L` exactly when:

```text
0 <= start <= end <= L
```

Its length is `end - start`. Since S3 lowering represents subtraction through
existing operations, no new opcode is required. A zero-length span is valid.
A span stores no text identity and cannot be dereferenced without an explicitly
supplied `BoundedText`.

## Structured Results And Errors

Operations that can fail return nominal structured results. The minimum types
are:

- `TextReadResult` for a code unit or an error/end condition;
- `TextAdvanceResult` for the next cursor or an error;
- `TextCompareResult` for a comparison result or an error;
- `TextError` carrying a stable numeric code, source span, and one bounded
  scalar detail when needed.

Stable error classes cover:

- invalid logical length;
- invalid padding or code unit;
- cursor before start or beyond end;
- read at end-of-input;
- advance beyond end-of-input;
- invalid span;
- lookahead beyond end-of-input;
- unsupported code unit.

There are no exceptions, hidden Python exception objects, implicit
propagation, stack unwinding, or `?` operator. S3 callers use explicit `match`
and `return`. Python reference code returns equivalent result records rather
than using exceptions for expected bounded-input failures.

## Pure Operations

Milestone 1.13 implements only the operations needed by the tokenizer/parser:

- logical length and empty check;
- start cursor, end check, and cursor position;
- current read, advance, and bounded peek;
- code-unit comparison and prefix recognition;
- span length, empty check, and validation;
- decimal digit classification;
- identifier-start classification;
- identifier-continuation classification.

All operations are deterministic, side-effect free, filesystem free, bounded
by capacity, and independent of mutable global state. They receive complete
values and return complete values.

`starts_with` receives explicit text, cursor, prefix text, and prefix span or
equivalent bounded values. Numeric scanning recognizes ASCII decimal digits
only. Identifier classification recognizes ASCII letters and underscore for
start, plus ASCII digits for continuation. No general-purpose string library,
case mapping, collation, formatting, or allocation API is introduced.

## Comparison And Scanning

Code-unit equality compares two validated scalar code units and returns the
existing S3 truth convention (`-1` true, `0` false). Prefix recognition compares
logical code units in order, never padding, and fails cleanly when the remaining
input is shorter than the requested prefix.

Decimal classification maps `48..57` to digit values `0..9` through a
structured result. Identifier classification is fixed to ASCII:

- start: `A..Z`, `a..z`, `_`;
- continuation: start set plus `0..9`.

The tokenizer owns accumulation and overflow checks for complete numeric
tokens. The bounded text layer only classifies one code unit at a time and
provides safe cursor movement.

## Copy-By-Value And Layout

`BoundedText`, cursors, spans, errors, and result enums use the canonical
`SemanticModel.fixed_value_layout(...)` contract. The `units` array contributes
cells `units.index0` through `units.index363` after the length cell. No helper
maintains parallel flattening or hidden array metadata.

Passing text copies all cells. A callee may reconstruct local memory for array
indexing under ADR-0023, but cannot observe or alias caller storage. Cursors and
spans remain small scalar records and never carry ownership or lifetime rules.

## Native Behavior

No native ABI extension is required. Expanded fixed-layout arguments use the
existing scalar register/stack argument sequence. Aggregate results use the
existing hidden sret convention. Array indexing uses existing local memory,
bounds checks, initialization checks, frame limits, and instruction limits.

The backend may use machine addresses internally for stack slots and sret, but
no address enters a source value. Native behavior must match the emulator for
result variant, code units, cursors, spans, and error codes.

## Deterministic Diagnostics

The self-hosted component's expected failures are data, not hosted diagnostics.
Error codes and spans are stable and deterministic. Malformed source values
that violate compiler type/layout rules remain ordinary deterministic compiler
diagnostics. Runtime bounds failures must not replace a structured result for
an operation whose public contract explicitly handles that bound.

Repeated calls with equal inputs produce equal results. Source-unit order does
not affect nominal layout, error codes, cursor positions, or spans.

## Explicitly Unsupported

This decision does not add:

- dynamic strings, arrays, or capacity;
- heap allocation or garbage collection;
- source pointers, references, borrowing, slices, or aliasing;
- implicit conversion from `string` to `BoundedText`;
- mutation of text values;
- UTF-8 decoding or full byte-domain text;
- Unicode, grapheme, locale, or normalization behavior;
- filesystem or language I/O;
- generic cursor/span/result types;
- exceptions or implicit error propagation;
- default self-hosted compiler behavior;
- IR or Assembly format changes.

## Alternatives Considered

### Pointer Plus Length

Rejected because it introduces reference semantics, lifetimes, aliasing, and a
new source-visible representation that the campaign explicitly excludes.

### Reuse The Static String Handle Directly

Rejected for runtime scanning. The handle deliberately hides storage and only
supports compile-time-known operations. Making it indexable at runtime would
broaden the 1.04 contract and expose native pointer concerns.

### Capacity 365

Rejected because the end cursor for full input would be 365, outside the
positive `tryte` range. Capacity 364 keeps all positions directly representable.

### Store Text Inside Cursor Or Span

Rejected because it duplicates a 365-cell value in every cursor/span, obscures
API dependencies, and still does not provide reference semantics.

### Dynamic Tokenizer Buffer

Rejected because the later tokenizer is incremental and needs only one token,
one cursor, and fixed-layout state at a time.

## Consequences

Positive:

- runtime scanning becomes expressible with existing fixed values;
- every bound and position is representable by one `tryte`;
- Python, emulator, and native implementations can share exact result data;
- tokenizer/parser components can remain incremental and allocation-free;
- existing static `string`, IR, Assembly, and bootstrap defaults remain stable.

Costs:

- values carry 364 padded cells even for short text;
- call scalarization is wide and relies on the aggregate ABI campaign;
- fixture construction is verbose and belongs in explicit differential
  harnesses rather than ordinary source ergonomics;
- accepted text is intentionally ASCII-only.

## Testing Strategy

After the Milestone 1.16 implementation gate, coverage must compare Python,
S3 emulator O0/O1, and native O0/O1 for empty, single-unit, full-capacity,
invalid-length, invalid-padding, invalid-code-unit, cursor, read, advance, peek,
span, prefix, digit, identifier, punctuation, repetition, imports, and
source-unit permutation cases.
