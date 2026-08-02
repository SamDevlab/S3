# ADR-0025: Bounded Assembly Parser And Frontend Boundary

Status: Accepted

## Context

Milestones 1.12 through 1.14 established fixed array values, bounded ASCII text,
and an incremental Assembly tokenizer. The next self-hosting step needs a parser
kernel and frontend candidate that can consume this bounded stream without
promoting S3 code to the default compiler path.

Python remains the reference compiler, reference Assembly parser, and default
artifact reader.

## Decision

The bounded parser/frontend architecture is event-driven, explicit, and
incremental:

1. The accepted input subset is textual S3 Assembly 0.6.0, plus legacy 0.5.0
   only where existing Python artifact reading already preserves width-one
   compatibility.
2. The parser consumes `BoundedText`, `TextCursor`, and `AssemblyTokenResult`
   values from the 1.14 tokenizer.
3. The tokenizer exposes `->` as a dedicated arrow token because function
   result groups are part of the existing Assembly syntax.
4. Parser state is an explicit fixed record. It contains phase, cursor,
   version, counters, current result width, and maximum observed result width.
5. Parser output is a structured result enum: event, end, or error.
6. Parser events are fixed-layout records. They do not carry source text,
   dynamic token lists, heap references, Python objects, or hidden state.
7. Parser errors are structured code/span/detail values. Tokenizer errors are
   nested only as data for diagnostics.
8. Lexical failures remain tokenizer failures. Syntax failures are parser
   errors. Whole-program semantic validation remains outside the parser kernel.
9. The parser recognizes version directives, function headers, declarations,
   block labels, `TCALL`, `TRET`, and `.end`.
10. Function result groups use the existing Assembly 0.6 bracket syntax.
11. `TCALL` destination groups model complete result groups, including the
    empty destination group used for full discard.
12. `TRET` operand groups model complete function result groups.
13. Local register typing, callee signatures, control-flow reachability,
    memory object validation, static string validation, and whole-program
    checks remain owned by the existing Python Assembly parser/verifier.
14. Unsupported directives, opcodes, punctuation, and future syntax must be
    rejected explicitly.
15. The frontend candidate composes tokenizer plus parser and returns a compact
    summary or parser error. It is not a replacement for `parse_assembly`.
16. S3 components are experimental differential references only.
17. No CLI path, golden artifact, public IR, S3 Assembly version, ABI,
    diagnostic schema, emulator behavior, native backend behavior, or package
    version changes.
18. No exceptions, implicit propagation, generic result type, heap allocation,
    dynamic strings, pointers, source-file handles, or filesystem access are
    introduced.
19. Tests for this campaign may be authored before the final validation gate,
    but must remain explicitly marked as created and not executed until the
    Milestone 1.16 implementation completes.
20. Any GitHub Actions results observed before 1.16 closes are early
    intermediate validation, not final campaign validation.

## Consequences

The parser/frontend path gives future self-hosting work a bounded Assembly
structure without changing the current compiler authority. It can be compared
against Python incrementally, while the full default parser remains unchanged.

The architecture intentionally accepts duplication between Python reference and
S3 experimental components. Adoption into default paths requires a later ADR and
separate validation campaign.
