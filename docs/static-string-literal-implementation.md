# Static String Literal Implementation Plan

## Purpose

This document defines the first implementable plan for real strings in S3:
static, immutable, deterministic string literals.

This delivery does not implement runtime strings. Double-quoted string literals
are reserved syntax with a front-end node today, and source programs that use
them still fail before lowering with a runtime-unsupported semantic diagnostic.
The goal here is to define the smallest future implementation slice that can
turn front-end literals into useful static values without exposing broad string
behavior.

## Current Behavior

Confirmed current behavior:

- `bootstrap/s3/lexer.py` defines `TokenKind.STRING_LITERAL`.
- `bootstrap/s3/lexer.py` scans a quoted literal from the opening quote through
  the closing quote and stores the original token text on the token.
- `bootstrap/s3/parser.py` builds a static string literal front-end expression
  for completed `TokenKind.STRING_LITERAL` tokens.
- `bootstrap/s3/static_strings.py` collects front-end string literal values into
  a deterministic static literal table.
- `bootstrap/s3/semantic.py` rejects that expression with
  `S3E_SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED` before lowering.
- `bootstrap/s3/diagnostics.py` defines
  `S3E_PARSE_UNSUPPORTED_STRING_LITERAL` and
  `S3E_SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED` and
  `S3E_LEX_UNTERMINATED_STRING_LITERAL`.
- `spec/diagnostics.md` lists both diagnostic codes.
- `tests/golden/diagnostics/unsupported_string_literal.json` covers the
  reserved literal diagnostic.
- `tests/golden/diagnostics/unterminated_string_literal.json` covers the
  lexical unterminated-literal diagnostic.

Confirmed absence:

- `bootstrap/s3/ast.py` has a string literal expression node but no string
  type.
- `bootstrap/s3/semantic.py` has no runtime string type checking.
- `bootstrap/s3/ir.py` has no string value type, string constant, or data
  section.
- `bootstrap/s3/assembly.py` renders Assembly text from Python strings, but
  Assembly does not model S3 runtime strings.
- `bootstrap/s3/emulator.py` and `bootstrap/s3/backends/` do not represent or
  execute string values.

## First Supported Behavior

The first future behavior should be deliberately narrow:

- A string literal creates a static immutable value.
- The initial accepted contents are an ASCII subset compatible with UTF-8.
- Literal contents are deterministic byte sequences.
- No general concatenation is exposed.
- No indexing is exposed.
- No length operation is exposed.
- No mutation is exposed.
- String parameters and returns are delayed unless the implementation proves
  they can be represented without widening the runtime surface.

The first useful context should be staged constant handling for deterministic
text production, especially future Assembly rendering helpers. This keeps the
feature valuable while preventing accidental claims of general-purpose string
support.

## Representation Decision

| Option | Advantages | Risks | Impact |
| --- | --- | --- | --- |
| Static literal table | Smallest useful representation for literals; can assign symbolic IDs; deterministic by construction | Does not solve dynamic text construction alone | Good first stage for parser, semantic checks, and hosted representation |
| IR string constant | Makes string values explicit in compiler artifacts | Requires IR schema changes and downstream support | Good second stage once the front-end contract is stable |
| Array of tryte or byte cells | Reuses the existing array direction conceptually | Current arrays are not first-class IR values and do not provide text semantics | Useful later for buffers, not enough for the first literal slice |
| Host-only bootstrap string | Fastest way to experiment in Python-hosted tooling | Can hide the real compiler contract and diverge from native behavior | Acceptable only as a temporary experiment, not the implementation target |
| Pointer plus length | Common runtime representation for strings and slices | Requires reference semantics, lifetime rules, and backend layout decisions | Too broad for the first supported behavior |

Recommended sequence:

1. Stage 1: introduce a static literal table with a symbolic string ID. The
   table owns front-end literal text and exposes stable IDs to later compiler
   phases.
2. Stage 2: add either an IR string constant or an explicit static data section
   when lowering needs to carry string data beyond the front end.

This path gives the future implementation a real compiler representation while
postponing runtime and native layout decisions until the surface is constrained
by tests.

## Compiler Impact Map

| Area | Future change | Risk | Notes |
| --- | --- | --- | --- |
| Lexer | Preserve token text and eventually define allowed escape handling | Medium | It already scans literals enough to reserve syntax. |
| Parser | Build a string literal expression for approved contexts instead of always rejecting | Medium | Unsupported contexts must still report a deliberate diagnostic. |
| AST | Add a string literal expression and likely a proposed string type name | Medium | Values must remain serializable and deterministic. |
| Semantic/typechecker | Assign the proposed string type and reject unsupported operations | Medium | This is where the narrow surface must be enforced. |
| Diagnostics | Narrow `S3E_PARSE_UNSUPPORTED_STRING_LITERAL` instead of deleting coverage | Medium | Existing goldens must be migrated intentionally. |
| IR | Add a string constant, symbolic literal reference, or static data record | High | This affects artifact stability and downstream consumers. |
| Assembly format | Decide whether string data is represented in Assembly artifacts | High | Current Assembly text is an output format, not a runtime string model. |
| Hosted emulator | Represent static strings only if a runtime path is added | High | The first runtime behavior should be hosted and deterministic. |
| Native backend | Either reject string runtime paths explicitly or implement data emission | High | Native layout should not be implied by front-end acceptance. |
| Tests | Add focused lexer, parser, semantic, diagnostic, and hosted tests | Medium | Keep tests small until runtime behavior exists. |
| Goldens | Update diagnostic and inspect goldens only when behavior changes intentionally | Medium | Existing inspect goldens must not drift as a side effect. |
| Docs | Keep the contract aligned with the implemented slice | Low | Avoid documenting broad support before it exists. |

## Diagnostic Migration

Today, any completed string literal used in expression position is parsed as a
static front-end expression and then rejected by semantic analysis with
`S3E_SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED`. An unterminated literal
remains a lexical error with `S3E_LEX_UNTERMINATED_STRING_LITERAL`.

In the first implementation stage:

- `S3E_LEX_UNTERMINATED_STRING_LITERAL` remains lexical and keeps covering
  unfinished quoted text.
- Valid static string literals are represented in the front-end only.
- Runtime use continues to use
  `S3E_SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED` until lowering and runtime
  representation exist.
- `S3E_PARSE_UNSUPPORTED_STRING_LITERAL` remains available for compatibility or
  parser-only unsupported contexts, but it is no longer the normal completed
  string-literal path.
- Existing diagnostic goldens are updated only with replacement coverage in the
  same implementation PR.

The important rule is that the unsupported diagnostic must not disappear before
there is a covered, intentional behavior for both accepted literals and rejected
string use.

## Type Model

The proposed minimal model is:

- Introduce a `string` type or equivalent type name when the implementation
  stage needs source-level annotation.
- A string literal has type `string`.
- A string value is immutable.
- A string is not numeric.
- A string does not implicitly convert to or from `trit`, `tryte`, arrays, or
  memory references.
- Equality and ordering are out of scope for the first stage.
- String parameters and return values may be delayed until representation and
  lifetime rules are stable.

This document proposes the type direction; it does not finalize surface syntax
beyond the already reserved double-quoted literal form.

## IR and Backend Strategy

Three implementation paths are available:

| Option | Description | Recommendation |
| --- | --- | --- |
| A | Add an IR string constant or symbolic literal reference and lower it first through hosted execution | Preferred once the front end accepts static literals |
| B | Keep strings only in front-end or host tooling for renderer bootstrap experiments | Useful only for prototypes, not for accepted language behavior |
| C | Add a data section that can carry static string bytes | Good long-term direction, likely after option A clarifies the contract |

The safest path is option A with a static literal table feeding a symbolic IR
string constant or reference. This does not block the future Assembly renderer:
fixed directives, names, opcodes, separators, and final newline text can be
modeled as deterministic literals before broader string operations exist.

The native backend should either reject unsupported string paths with a clear
internal limitation or implement explicit static data emission. It should not
silently ignore string data or imply runtime support before layout is defined.

## Static Literal Table

The current front-end table assigns IDs as `s0`, `s1`, `s2`, in first occurrence
order. Identical literal values reuse the first entry. The table is collected
from the AST only; it does not call semantic analysis, lowering, IR generation,
Assembly generation, or any backend. Runtime string support remains blocked by
`S3E_SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED`.

0.11-A adds a deterministic static text foundation around that table. Entries
keep the existing raw literal value and stable IDs, while exposing calculated
decoded text, LF-normalized UTF-8 bytes, byte count, line count, and SHA-256
metadata. Supported escapes are `\\`, `\"`, and `\n`; unsupported escapes fail
through the static text helper rather than through semantic diagnostics. This
does not make string literals executable or lowerable.

0.11-B adds `StaticTextBuilder` and `StaticTextDocument` for deterministic text
composition. The builder appends already-decoded text, raw static literals using
the 0.11-A decoder, and LF-terminated lines. Finalized documents expose
normalized text, UTF-8 bytes, byte count, line count, and SHA-256. No files are
created, no renderer output is generated, and source string literals remain
blocked by the semantic runtime diagnostic.

0.11-C adds `StaticTextLineEmitter`, a small structured layer that uses the
builder to emit LF-terminated lines, blank lines, raw static literal lines, and
controlled indentation. It finalizes to the same `StaticTextDocument` type and
keeps all metadata deterministic. It still does not render real Assembly
programs or produce fixture actual outputs.

## Test Plan

When implementation begins, add focused tests for:

- Lexer preservation or decoding of literal contents.
- Parser acceptance in the chosen first context.
- Parser or semantic rejection in unsupported contexts.
- Type checking that assigns the proposed `string` type.
- No implicit numeric conversion.
- Continued lexical handling for unterminated string literals.
- Hosted representation of static string literals if a hosted runtime path is
  added.
- Intentional diagnostic golden migration.
- Inspect golden stability unless the implementation intentionally changes
  inspected artifacts.

Avoid broad matrices until the runtime surface is larger. The first tests should
prove only the staged contract.

## Relationship to Assembly Renderer

Static string literals are useful for deterministic Assembly text because the
future renderer needs exact output for:

- Fixed directives such as `.s3asm`, `.function`, `.register`, `.label`, and
  `.end`.
- Opcode text.
- Function, register, and label names.
- Separators such as spaces, comma-space, and blank lines.
- The mandatory final newline.

Static literals alone are not enough for a full renderer. The renderer also
needs structured instruction data, deterministic ordering, formatting helpers,
and a real Python-vs-S3 comparison path. Static literals are the first text
building block, not the complete renderer.

## Out Of Scope

This plan does not include:

- General concatenation.
- Dynamic allocation.
- Full Unicode handling.
- Regular expressions.
- File I/O.
- String mutation.
- String slicing.
- First-class string arrays.
- A real S3 Assembly renderer.
- Native backend behavior changes.

## Acceptance Criteria For Implementation PR

A future implementation PR should be accepted only when:

- The accepted behavior is limited and explicit.
- Old diagnostics are migrated with replacement goldens.
- Unsupported string contexts remain covered.
- `python -m pytest -ra` passes.
- `python tools/golden_diagnostics.py check` passes.
- `python tools/golden_inspect.py check` passes.
- Hosted behavior is covered if any runtime path is added.
- Native limitations are documented or implemented.
- No false support for broad string behavior is exposed.

## Next Recommendations

For 0.10-O, implement the first real slice: AST and semantic/typechecker support
for static string literals, backed by a static literal table and still without
broad native backend support.

For 0.10-P, add deterministic text-building helpers or literal-table integration
for the future renderer path, then connect them to the renderer comparison
harness when the S3 renderer exists.
