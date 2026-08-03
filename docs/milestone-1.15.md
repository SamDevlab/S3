# Milestone 1.15 - Bounded Assembly Parser Kernel

Status: Implementation complete; consolidated campaign validation deferred.

## Boundary

Milestone 1.15 adds an experimental bounded Assembly parser kernel for the
self-hosting path. It consumes the 1.14 tokenizer and emits one structured event
or one structured error per call.

The normative architecture is
[ADR-0025](decisions/ADR-0025-bounded-assembly-parser-frontend.md).

This parser is not the default Assembly parser and does not replace
`bootstrap.s3.assembly.parse_assembly`.

## Parsed Subset

The kernel recognizes the minimum Assembly 0.6 syntax needed to structure the
next frontend step:

- `.s3asm 0.6.0`;
- legacy `.s3asm 0.5.0` at the bounded artifact boundary only;
- `.function name -> type` and bracketed result type groups;
- `.param`, `.register`, and `.memory` declaration lines as structural
  declarations;
- `.label name`;
- `TCALL` lines with result destination groups;
- `TRET` lines with result operand groups;
- `.end`.

The tokenizer now exposes `->` as an explicit `ARROW` token because function
headers already use that Assembly syntax.

## Implementation

- Python reference: `bootstrap/s3/assembly_parser_kernel.py`;
- S3 result types: `selfhost/assembly/parser_types.s3`;
- S3 parser: `selfhost/assembly/assembly_parser.s3`;
- deferred tests: `tests/test_assembly_parser_kernel.py`.

The parser state is an explicit record containing phase, cursor, version,
counters, current function result width, and maximum observed result width.
Events and errors are fixed-layout values.

## Static Gate Inventory

| Area | Classification | Evidence |
| --- | --- | --- |
| ADR | IMPLEMENTED | ADR-0025 accepted |
| Token dependency | IMPLEMENTED | tokenizer exposes `ARROW` for `->` |
| Python parser kernel | IMPLEMENTED | bounded incremental event parser |
| S3 parser types | IMPLEMENTED | fixed state, event, error, result records/enums |
| S3 parser | IMPLEMENTED | consumes tokenizer result values explicitly |
| TCALL/TRET groups | IMPLEMENTED | structural width/discard metadata |
| Whole-program semantics | NOT APPLICABLE | remain owned by Python parser/verifier |
| Default path | NOT APPLICABLE | no default parser activation |
| Tests authored | IMPLEMENTED | focused parser/token-boundary coverage |
| Validation | DEFERRED | no execution before the 1.16 campaign gate |

## Coverage Status

Coverage is authored for the arrow token, version event, function header event,
declaration event, label event, `TCALL`, `TRET`, `.end`, unsupported version,
missing arrow, parser source availability, and S3 parser source availability.

EXECUTED DURING CONSOLIDATED CAMPAIGN VALIDATION

## Deferred Validation

Final local validation executed the parser kernel tests, the 1.14-1.16 focused
group, the local unit selector, the full pytest suite, compileall, golden
inspect, renderer comparison, and diff checks after Milestone 1.16 implementation
completed. Native ELF execution remains represented by the Linux CI job.

MILESTONE 1.15 - IMPLEMENTATION COMPLETE

CONSOLIDATED VALIDATION EXECUTED
