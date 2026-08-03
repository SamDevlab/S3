# Milestone 1.13 - Bounded Text, Cursors, And Spans

Status: Implementation complete; consolidated campaign validation deferred.

## Boundary

Milestone 1.13 adds bounded operational text for self-hosted tokenizer/parser
components. It does not broaden the compile-time `string` handle into a runtime
string API. The normative decision is
[ADR-0024](decisions/ADR-0024-bounded-text-cursors-and-spans.md).

## Representation

`BoundedText` contains a logical `tryte` length and a `tryte[364]` code-unit
array. Input accepts ASCII tab, LF, CR, and printable code units. Cells after
the logical end are zero padding. Capacity 364 keeps the full-input end cursor
representable by one `tryte`.

`TextCursor` contains only a position. `SourceSpan` contains half-open start/end
indices. Neither contains text, memory identity, a handle, pointer, or implicit
reference. Operations receive text explicitly.

## Structured Operations

The S3 component provides pure bounded operations for length, emptiness,
validation, cursor start/end/position, current read, advance, peek, code-unit
comparison, prefix recognition, span length/emptiness/validation, decimal digit
classification, and identifier start/continuation classification.

Expected failures use `TextReadResult`, `TextAdvanceResult`,
`TextCompareResult`, and stable `TextError` values. Propagation is explicit by
`match`; no exceptions or implicit operator are introduced.

Consumers validate each incoming text once with `validate_text` before
scanning. Individual operations then enforce cursor and lookahead bounds
without repeatedly traversing the complete fixed-capacity representation.

## Implementations

- Python reference: `bootstrap/s3/bounded_text.py`;
- nominal S3 types: `selfhost/text/bounded_text_types.s3`;
- S3 operations: `selfhost/text/bounded_text_primitives.s3`.

The implementations are independent. Python remains the compiler reference and
default. The S3 component is an experimental differential reference.

## Static Gate Inventory

| Area | Classification | Evidence |
| --- | --- | --- |
| ADR | IMPLEMENTED | ADR-0024 accepted |
| Representation | IMPLEMENTED | fixed 364-cell ASCII text plus logical length |
| Cursor | IMPLEMENTED | nominal scalar-index `TextCursor` |
| Span | IMPLEMENTED | nominal half-open `SourceSpan` |
| Bounds | IMPLEMENTED | length, cursor, peek, span, code-unit, and padding contracts |
| Operations | IMPLEMENTED | tokenizer-oriented pure operation set |
| Structured errors | IMPLEMENTED | stable code/span/detail and explicit result enums |
| Python reference | IMPLEMENTED | pure independent bounded text module |
| S3 implementation | IMPLEMENTED | imported nominal types and primitive module |
| Imports | IMPLEMENTED | explicit module/type/function imports in authored corpus |
| Native compatibility | NOT APPLICABLE | existing fixed-array arguments and hidden sret apply by construction |
| Tests authored | IMPLEMENTED | Python, emulator O0/O1, native O0/O1, permutations |
| Documentation | IMPLEMENTED | language, memory, self-hosting, roadmap, README, and this plan |

## Coverage Status

Coverage is authored for empty, one-unit, full-capacity, invalid length,
unsupported code unit, invalid padding, cursor start/end, current read,
advance, repeated movement, peek, overrun, invalid cursor, empty/full/invalid
spans, prefix success/failure, decimal digits, identifiers, punctuation,
deterministic repetition, imported helpers, source-unit permutations, Python,
emulator O0/O1, and native O0/O1.

EXECUTED DURING CONSOLIDATED CAMPAIGN VALIDATION

## Explicit Limits

No dynamic capacity, heap, source pointer/reference, aliasing, mutation,
filesystem, Unicode, full UTF-8 decoding, grapheme behavior, locale,
normalization, generics, exceptions, format bump, or default activation is
included.

MILESTONE 1.13 - IMPLEMENTATION COMPLETE

CONSOLIDATED VALIDATION EXECUTED
