# S3 0.11 Roadmap

Status: closed

## Objective

S3 0.11 established the deterministic static text foundation needed for future
textual compiler output. It moved the project from renderer-candidate-only
contracts into small, testable implementation layers that can later support a
real Assembly renderer output path.

0.11 is complete after 0.11-C. There is no 0.11-D planned. The next milestone
starts actual-output work.

## Completed sequence

### 0.11-A: deterministic static text foundation

0.11-A added deterministic static text helpers for front-end string literal
contents. The helpers decode the supported escapes `\\`, `\"`, and `\n`,
normalize newlines to LF, encode UTF-8 bytes, and expose byte count, line count,
and SHA-256 metadata.

This was a foundation layer only. It did not implement the S3 Assembly renderer
and did not create fixture actual outputs.

### 0.11-B: deterministic static text builder/document

0.11-B added `StaticTextDocument` and `StaticTextBuilder` so future renderer
work can compose byte-stable documents before fixture actual outputs exist.

The builder starts empty, appends decoded text, appends raw static literals
through the same decoder, appends LF-terminated lines, and finalizes to a
document exposing normalized text, UTF-8 bytes, byte count, line count, and
SHA-256 metadata.

### 0.11-C: deterministic static text line emitter

0.11-C added `StaticTextLineEmitter`, a line-oriented layer on top of the static
text builder. It emits LF-terminated text lines, blank lines, raw static literal
lines through the existing decoder, and controlled indentation.

The emitter finalizes to the same `StaticTextDocument` type and keeps the
document text, UTF-8 bytes, and metadata deterministic.

## Delivered

0.11 delivered:

- deterministic static text representation;
- deterministic UTF-8 bytes;
- LF newline normalization;
- `byte_count`, `line_count`, and `sha256` metadata;
- `StaticTextDocument`;
- `StaticTextBuilder`;
- `StaticTextLineEmitter`;
- structured line-based text composition;
- a foundation for future textual output.

## Not delivered

0.11 did not:

- implement the real S3 renderer;
- create actual outputs;
- create `tests/golden/assembly_renderer_candidate_actual`;
- unblock broad string lowering or runtime support;
- alter inspect goldens;
- alter the backend or emulator.

## Next milestone

S3 0.12 uses this deterministic text foundation to begin practical
actual-output work. The initial focus is the `first` fixture; see
`docs/roadmap-0.12.md`.
