# Milestone 1.14 - Incremental Assembly Tokenizer

Status: Implementation authored; validation pending.

## Boundary

Milestone 1.14 adds an experimental incremental tokenizer for the bounded S3
Assembly subset consumed by the next parser milestone. It is not the default
Assembly parser and does not replace `bootstrap.s3.assembly.parse_assembly`.

The tokenizer receives `BoundedText` and an explicit `TextCursor`, skips
horizontal whitespace, and returns at most one structured result per call:
token, end-of-input, or error. Results carry exact half-open `SourceSpan`
coordinates and the next cursor. The component stores no source pointer,
reference, slice, dynamic token list, heap value, hidden parser state, global
cache, filesystem handle, or Python runtime object.

## Lexical Subset

The tokenizer recognizes the textual Assembly forms already used by Assembly
0.6 and legacy scalar Assembly 0.5:

- `.s3asm` as `VersionDirective`;
- known directives `.function`, `.param`, `.register`, `.memory`, `.label`,
  `.data`, and `.end` as directive ids;
- version numbers shaped as `MAJOR.MINOR.PATCH` with one decimal digit per
  component;
- identifiers for functions, labels, opcodes, and type names;
- `rN` as register names;
- `mN` and `sN` as value names;
- signed decimal integers in the current single-tryte scalar range;
- `:`, `,`, `=`, brackets, parentheses, LF, CRLF, and `;` comments.

Opcode names such as `TCALL` and `TRET` remain lexical identifiers. The parser
milestone classifies opcode semantics.

## Structured Errors

Errors are data and use exact spans:

- unexpected code unit;
- malformed integer;
- integer overflow;
- invalid directive;
- invalid identifier or name prefix;
- cursor out of bounds;
- truncated token;
- unsupported token.

No S3 exception mechanism or implicit propagation is introduced.

## Implementations

- Python reference: `bootstrap/s3/assembly_tokenizer.py`;
- S3 result types: `selfhost/assembly/tokenizer_types.s3`;
- S3 tokenizer: `selfhost/assembly/assembly_tokenizer.s3`;
- corpus and differential coverage: `tests/test_assembly_tokenizer.py`.

The Python compiler, Python Assembly parser, IR 0.6.0, and Assembly 0.6.0
remain the reference/default paths.

## Preventive Impact Inventory

Existing Assembly parser, emulator, renderer, golden, fixture, and benchmark
contracts were evaluated before validation. The tokenizer is additive and
experimental, so existing parser rejection behavior, renderer output, goldens,
fixtures, benchmark thresholds, and `parse_assembly` diagnostics remain
unchanged.

## Maturity

Maturity: experimental differential reference.

MILESTONE 1.14 - IMPLEMENTATION COMPLETE

CONSOLIDATED CAMPAIGN VALIDATION DEFERRED
