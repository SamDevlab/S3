# Minimal String Contract for Self-Hosting

## Purpose

This document defines the smallest future string contract needed for partial
self-hosting work, especially the Assembly renderer subset.

Strings are not runtime values in S3 today. Double-quoted string literals are
recognized by the lexer as reserved syntax, parsed as static front-end
expressions, then rejected by semantic analysis with a structured diagnostic.
Python remains the reference implementation for the compiler and for Assembly
rendering. This delivery documents a target contract; it does not implement
runtime strings.

## Current State

Confirmed source behavior:

- `bootstrap/s3/lexer.py` defines `TokenKind.STRING_LITERAL`.
- `bootstrap/s3/lexer.py` scans double-quoted literals enough to find the
  closing quote.
- `bootstrap/s3/parser.py` builds a string literal expression for completed
  `STRING_LITERAL` tokens.
- `bootstrap/s3/semantic.py` rejects string literal expressions before lowering
  because runtime support is not implemented.
- `bootstrap/s3/diagnostics.py` defines:
  - `S3E_PARSE_UNSUPPORTED_STRING_LITERAL`
  - `S3E_SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED`
  - `S3E_LEX_UNTERMINATED_STRING_LITERAL`
- `spec/diagnostics.md` lists both public diagnostic codes.
- `tests/golden/diagnostics/unsupported_string_literal.json` covers the
  semantic runtime-unsupported diagnostic.
- `tests/golden/diagnostics/unterminated_string_literal.json` covers the
  unterminated literal diagnostic.

Confirmed absence:

- There is no source-level `string` type.
- `bootstrap/s3/ast.py` has a string expression node but no string type.
- `bootstrap/s3/semantic.py` has no runtime string type checking.
- `bootstrap/s3/ir.py` only has `trit` and `tryte` value types.
- `bootstrap/s3/assembly.py` only models Assembly text as Python strings in the
  hosted renderer, not as S3 runtime string values.
- `bootstrap/s3/emulator.py` and `bootstrap/s3/backends/x86_64/` do not execute
  a string runtime.

## Why Strings Are Required

The Assembly renderer subset must produce deterministic text. It needs strings
to emit:

- directives such as `.s3asm`, `.function`, `.register`, `.label`, and `.end`;
- function names;
- register names;
- labels;
- opcode text;
- separators such as comma-space;
- indentation;
- source comments;
- blank lines;
- the mandatory final newline.

The renderer acceptance criterion is byte-for-byte equality with the Python
reference in `bootstrap/s3/assembly.py`. Numeric-only values are not enough for
that target because the observable artifact is text.

## Minimal Semantic Model

Required for the first renderer subset:

- A string is an immutable sequence of bytes in a deterministic encoding.
- A string literal creates a constant string value.
- String values may be appended to a deterministic output buffer.
- Output finalization produces exact text with preserved spaces and newlines.
- The existing unsupported-string diagnostic is replaced or narrowed only when
  the new behavior is actually implemented.

Useful later:

- General concatenation.
- String length.
- Indexing by byte or scalar value.
- Structural equality.
- Formatting of numeric values.
- Escape decoding beyond the minimal literal grammar.

Out of scope for the first renderer subset:

- Interpolation.
- Unicode normalization.
- Regular expressions.
- General dynamic allocation.
- Broad file I/O.
- Locale-aware behavior.

## Encoding Decision

The recommended starting point is an ASCII-compatible UTF-8 byte sequence.

0.11-A starts this path with deterministic static text helpers for front-end
string literal contents. The helpers decode the supported escapes `\\`, `\"`,
and `\n`, normalize newlines to LF, encode UTF-8 bytes, and expose byte count,
line count, and SHA-256 metadata. This is not runtime string support, does not
make string literals lowerable, and does not create renderer actual outputs.

0.11-B adds deterministic static text composition. A builder can append decoded
text, raw static literals through the same decoder, and LF-terminated lines,
then finalize to a document exposing normalized text, UTF-8 bytes, and the same
metadata. This remains an internal compiler foundation, not source-level string
runtime support.

For the first implementation, it is acceptable to validate only the ASCII subset
needed by the Assembly renderer fixtures, while keeping the representation and
terminology compatible with UTF-8 bytes.

Rationale:

- The current Assembly text, directives, opcodes, register names, labels, and
  source comments are ASCII.
- UTF-8 is compatible with Python text files and committed goldens.
- Byte-oriented comparison supports deterministic artifact checks.
- A tryte/trit-specific string encoding would add conversion rules before the
  renderer has any need for them.

## Representation Options

| Option | Advantages | Risks | IR impact | Emulator impact | Native backend impact | Fit for renderer subset |
| --- | --- | --- | --- | --- | --- | --- |
| Fixed-size array of byte-like cells | Reuses the existing fixed-size array direction conceptually | Current arrays cannot be parameters, returns, nested, or first-class IR values | Could reuse memory objects but would still need a byte/string type story | Could reuse memory checks but needs string operations | Could reuse memory layout but needs text output ABI decisions | Useful for fixed buffers, not enough alone |
| Pointer plus length | Common representation for slices and buffers | Requires pointer or reference semantics not present today | Requires new reference-like value representation | Requires managed memory or frame lifetime rules | Requires ABI and layout decisions | Too broad for the first step |
| Static string table | Simple for literals and renderer keywords | Does not solve dynamic output construction by itself | Requires static data or string constant references | Requires table lookup and append/read operations | Requires static data emission or hosted-only limitation | Strong candidate for literals |
| Host-only bootstrap string | Fastest way to validate renderer behavior | Cannot become self-hosted without replacement | Could avoid IR initially, but that hides the real target | Hosted-only behavior would diverge from native | Native support would be absent or explicitly unsupported | Good only as a temporary experiment |
| Dedicated IR string constant | Explicit and deterministic | Requires IR/schema/version changes | Adds a real string value surface | Requires runtime support | Requires data emission or runtime helpers | Strong long-term direction |

Recommended path: start with static literal storage plus a deterministic append
buffer. Keep the encoding byte-oriented and ASCII-compatible, then introduce a
dedicated IR string constant or static data section when implementation begins.

## Minimal Operations

Required first:

- Store a string literal.
- Append a literal to a builder or output buffer.
- Append a single space.
- Append a newline.
- Append a known identifier/name.
- Join known lines deterministically.
- Finalize to output text.
- Compare output byte-for-byte against committed expectations.

Later:

- General concatenation.
- Substring or slicing.
- Length.
- Indexing.
- Structural comparison.
- Formatting decimal numbers.
- Escape rendering.

Out of scope:

- Unicode normalization.
- Regex-like matching.
- General dynamic allocation.
- Broad file I/O.
- Runtime text parsing.

## Interaction With Existing Arrays

Arrays already exist in S3 and are documented in
`docs/array-capabilities.md`. They can help model fixed buffers and ordered
collections, but they do not solve strings alone.

Relevant current limitations:

- Arrays lower to memory and are not first-class IR values.
- Arrays cannot be function parameters.
- Functions cannot return arrays.
- Nested arrays are rejected.
- There is no dynamic vector growth.
- Whole-array assignment is rejected.

For the Assembly renderer subset, arrays may help hold ordered functions,
registers, blocks, instructions, labels, or buffer cells. Real string support
still needs a value model, append/finalization operations, and deterministic
text comparison.

## Required Implementation Stages

Stage 1: keep string literals reserved and diagnostics stable.

Stage 2: add a source-level `string` type in semantic analysis, still without
full lowering.

Stage 3: add an IR representation for string literals, such as a string
constant or static data reference.

Stage 4: add hosted emulator support for the minimal operations required by
deterministic rendering.

Stage 5: decide whether the native backend supports the same string subset or
whether early string experiments remain explicitly hosted-only.

Stage 6: add deterministic formatting helpers for spaces, newlines, names,
opcodes, and line joining.

Stage 7: use those helpers in an S3 Assembly renderer subset and compare its
output against the Python renderer.

## Impact Map

| Area | Future change needed | Risk | Notes |
| --- | --- | --- | --- |
| Lexer | Decode or preserve literal contents intentionally | Medium | It currently scans literals only enough to reserve syntax. |
| Parser | Build a string expression node instead of rejecting the token | Medium | The old unsupported diagnostic must be adjusted intentionally. |
| AST | Add a string literal expression and likely a string type node | Medium | Must stay serializable and deterministic. |
| Typechecker/semantic analysis | Validate string type use and operation signatures | Medium | Avoid accidentally allowing broad text behavior too early. |
| IR | Represent string constants or static data references | High | IR format/versioning may be affected. |
| Assembly format | Decide whether Assembly text models string data | High | Current Assembly is textual output, not a string runtime format. |
| Hosted emulator | Execute string constants and append/buffer operations | High | Needs memory/lifetime rules for deterministic behavior. |
| Native backend | Emit or reject string support explicitly | High | Data layout and ABI choices are larger than the initial contract. |
| Tests | Add focused unit, golden, and renderer comparison tests | Medium | Existing diagnostics goldens will need intentional updates. |
| Goldens | Preserve deterministic output across inspect and diagnostics | Medium | Byte-for-byte text comparison remains the acceptance model. |
| Docs | Keep the contract aligned with implementation stages | Low | Avoid promising broad string semantics before they exist. |

## Acceptance Criteria For Real String Support

Future real string support is not complete until:

- string literals compile as values in an intentionally scoped program;
- `string` is validated by semantic analysis;
- the unsupported-string diagnostic is removed or narrowed intentionally;
- IR represents string data deterministically;
- hosted execution can manipulate the minimal subset;
- diagnostics goldens are updated intentionally;
- inspect/golden outputs remain deterministic;
- native support is implemented or explicitly rejected with a stable diagnostic;
- the Assembly renderer subset can use strings without depending on Python for
  text construction.

## Next Recommendations

- 0.10-K: inventory or contract records/structs and enums for representing
  `AssemblyInstruction`-like data.
- 0.10-L: define an `AssemblyProgram` data contract using existing arrays,
  future strings, and future records/enums.
- 0.10-M: start the first real string implementation at the smallest safe layer,
  either semantic typing or IR representation, depending on the chosen
  representation.
