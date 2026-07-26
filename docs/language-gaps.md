# S3 Language Gap Inventory

This document maps the language gaps that block gradual migration of compiler
components from Python to S3. It does not define final syntax and does not
promise immediate self-hosting. The Python compiler remains the reference
implementation while these gaps are closed.

## Objetivo

The goal is to compare three things:

- what the Python compiler uses today;
- what the S3 language can express today;
- what S3 must express before real compiler components can move from Python to
  S3.

The inventory is intentionally practical. Each gap is tied to compiler
components, migration risk, and a recommended next delivery.

## Prioridades

P0:

Required before the first real compiler component can be migrated to S3.

P1:

Required before larger compiler components can be migrated safely.

P2:

Required for broader self-hosting and wider tooling, after the first component
comparison path is working.

## Matriz de gaps da linguagem

| Resource | Priority | Why it is needed | Components unlocked | Current status | Minimal desired example | Risks | Recommended next delivery |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Strings | P0 | Compiler components need names, source text slices, rendered Assembly, diagnostic messages, and serialized artifacts. | lexer, diagnostics, Assembly renderer, diagnostic formatter | S3 0.53 supports first-class typed static text values only; dynamic construction, concatenation, indexing, comparison, formatting, file I/O, and broad text operations are not available. | static `string` literal handle plus future concatenation | Text rules can become large quickly. | Specify the next minimal text operation required by a selected migration target. |
| Arrays or vectors | P0 | Compiler data is ordered: tokens, blocks, instructions, registers, notes, and arguments. | token streams, IR lists, Assembly lists, diagnostics | Static arrays exist, but compiler components need reusable ordered collections. | array of `tryte` and vector-like append/read operations | Dynamic growth and bounds rules can complicate runtime behavior. | Specify minimal vector operations or a constrained fixed-array subset. |
| Reusable helper functions | P0 | Early migrated code should share formatting, normalization, and comparison helpers. | Assembly renderer, IR normalizer, small static checker | Functions exist, but reusable multi-file organization is limited. | shared pure helper called from two small functions | Duplication grows if helpers cannot be organized. | Define a small helper-library convention for single-file examples first. |
| Program tests for S3 code | P0 | Migrated components need automated tests independent of Python implementation details. | all migrated components | End-to-end tests exist for compiler behavior, not a dedicated S3 component test harness. | compile a small S3 program and compare return or output artifact | Tests can become brittle if they compare unstable details. | Add a minimal S3 program test pattern using existing CLI utilities. |
| Records or structs | P1 | Compiler data has named fields: tokens, spans, IR instructions, Assembly functions, diagnostics. | AST model, IR model, Assembly model, diagnostics | Not available as first-class user data. | conceptual record with named fields | Layout, mutability, and equality rules need clear contracts. | Design immutable records with field access. |
| Enums or sum types | P1 | Token kinds, AST variants, opcodes, types, and diagnostic categories need closed alternatives. | lexer, parser, IR, Assembly, diagnostics | Not available as first-class user data. | conceptual opcode enum | Variant payloads can make the feature too broad at first. | Start with simple enums before payload-carrying variants. |
| Stable pattern matching | P1 | Compiler code needs clear branching over variants and nested data. | parser, lowering, verifier, optimizer | `match` exists for current control-flow use, but not as a complete data-decomposition tool. | conceptual match over an enum value | Exhaustiveness and payload binding must be precise. | Stabilize matching over simple enums before nested structures. |
| Modules and imports | P1 | Compiler code must be split into reusable files with explicit dependencies. | any multi-file component, helper libraries | Not available as a compiler feature. | conceptual import of a pure helper function | Path resolution can affect reproducibility. | Specify deterministic local module resolution. |
| Minimal standard library | P1 | Common operations should not be copied into every component. | renderers, normalizers, comparison tools | Not available as a defined S3 library. | small pure helper module for string or array utilities | Library scope can expand without clear needs. | Add only helpers required by selected migration candidates. |
| Structural comparison | P1 | Python-vs-S3 comparison needs equality over nested data, not only scalar return values. | comparison harness, IR normalizer, diagnostic formatter | Scalar comparisons are possible; compound structural equality is not generally available. | compare two conceptual records for equality | Equality over mutable or nested data can hide costs. | Define deterministic equality for immutable records and arrays. |
| Deterministic serialization | P1 | Golden comparison depends on stable text or structured output. | IR serializer, diagnostic formatter, Assembly renderer | Assembly and IR are serialized by Python tools, not S3 code. | render a small record to stable text | Formatting drift can look like semantic drift. | Start with a small text renderer for one data shape. |
| Structured diagnostics in S3 | P1 | Migrated components must report compatible category, code, phase, location, and message data. | parser, semantic analysis, verifier, static checker | Python owns structured diagnostics today. | construct a conceptual diagnostic record | Error handling can diverge from Python reference behavior. | Define a minimal diagnostic data record before formatter migration. |
| Maps or equivalent lookup | P1 | Name tables, register tables, memory objects, and labels need keyed lookup. | semantic analysis, verifier, emulator, parser | Not available as a general user-level data structure. | conceptual insert and lookup by symbol | Hashing and ordering can threaten determinism. | Prefer deterministic association lists first, then maps if needed. |
| Clear update and mutability rules | P1 | Compiler passes need predictable updates to data without hidden aliasing. | IR normalizer, optimizer, semantic analysis | S3 has explicit `mut` for current values, but compound update rules are not enough for compiler data. | conceptual update of a record or vector element | Aliasing rules can affect correctness and comparison. | Define simple immutable-by-default compound data with explicit updates. |
| Controlled file I/O | P2 | Tooling eventually needs to read source, artifacts, and comparison fixtures. | golden tools, CLI-like tools, comparison harness | Not available to S3 programs. | read one text file and write one generated artifact | Host behavior can reduce reproducibility. | Keep I/O behind a narrow host boundary after pure components work. |

## Gaps por componente do compilador

| Python component | First migratable subset | Required S3 resources | Critical missing resources | Risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| Assembly renderer | Render a small Assembly function from a simple data shape. | strings, arrays, records, reusable helpers, deterministic serialization | records, deterministic formatting helpers | medium | Strong early candidate. Text output can be compared exactly. |
| IR normalizer | Normalize a small IR-like structure into canonical order or text. | arrays, records, structural comparison, deterministic serialization | records, structural comparison | medium | Strong early candidate after records exist. |
| Diagnostic formatter | Format a diagnostic record into stable text or JSON-like text. | strings, records, enums, deterministic serialization | records, enums, deterministic formatting helpers | medium | Strong early candidate if diagnostic shape is kept small. |
| Small static checker | Check one narrow invariant over a small data structure. | arrays, records, enums, program tests | records, enums | medium | Good candidate if the invariant has a compact contract. |
| Lexer | Tokenize a restricted source fragment. | strings, arrays, diagnostics, source spans | strings, arrays, diagnostics | high | Do not start with the full lexer. Consider only tiny experiments later. |
| Parser | Parse a restricted token sequence. | arrays, recursive data, enums, pattern matching, diagnostics | recursive structures, enums, pattern matching | very high | Poor first target. Wait until data modeling is mature. |
| Semantic analysis | Validate a small symbol table rule. | records, arrays, maps or association lists, diagnostics | maps or equivalent lookup, structured diagnostics | high | Wait until lookup and diagnostic records exist. |
| Lowering | Convert a tiny AST fragment to a tiny IR fragment. | AST records, IR records, arrays, diagnostics | records, enums, diagnostics | high | Later candidate after AST and IR shapes are available in S3. |
| Optimizer | One local canonicalization rule. | IR records, structural comparison, verification, tests | compound updates, comparison, verifier support | very high | Do not start here; regression risk is high. |
| Emulator | Execute one very small Assembly subset. | Assembly records, arrays, runtime state, errors | compound data, structured errors, maps | very high | Poor early target because behavior surface is large. |
| Native backend | Render a tiny native text fragment from Assembly data. | strings, records, target contracts, deterministic rendering | strings, records, platform contracts | very high | Not an initial target. Keep native behavior in Python. |
| CLI | No initial migration subset recommended. | file I/O, arguments, diagnostics, host boundary | file I/O, host integration | high | Keep in Python until S3 component comparison is proven. |
| Golden tools | Compare one generated S3 text artifact with expected text. | strings, file I/O, diffing, deterministic output | strings, file I/O | medium | Keep Python initially; later use as a S3 tool experiment. |

The strongest initial candidates are the Assembly renderer, IR normalizer,
diagnostic formatter, and a small static checker. The weakest starting points
are the full parser, full lexer, optimizer, native backend, full emulator, and
complete CLI.

## Minimos exemplos desejados

The examples below are conceptual. They are not final syntax unless the relevant
feature already exists.

| Gap | Useful minimal example | Notes |
| --- | --- | --- |
| String literal and concatenation | Build `"TRET " + register_name`. | Needed by renderers and diagnostics. |
| Array of trytes | Store a short ordered list and read by index. | Current fixed arrays help, but compiler data needs reusable collection patterns. |
| Record | Represent `{ line, column, offset }` for a source span. | Records unlock named compiler data. |
| Enum | Define an opcode-like closed set: `TCONST`, `TRET`. | Start without payloads. |
| Match over enum | Branch on a simple opcode enum. | Needed before richer pattern matching. |
| Module import | Import a pure helper function from another file. | Needed for non-trivial component organization. |
| Shared pure helper | Reuse a formatting helper from two functions. | Prevents copying helper code into every experiment. |
| Simple serialization | Render a small record into deterministic text. | First step toward Python-vs-S3 comparison. |
| Structural comparison | Compare two span records or two small instruction records. | Required for component tests and comparison harnesses. |

Conceptual fixtures can live under `examples/gaps/` with a `.s3.txt` extension
so existing compiler tests do not treat them as runnable S3 programs.

## Ordem recomendada de implementacao da linguagem

1. Minimal strings.
2. Arrays or vectors for reusable ordered data.
3. Records or structs with named fields.
4. Enums or sum types.
5. Stable pattern matching over simple variants.
6. Minimal modules and imports.
7. Minimal standard library helpers.
8. Deterministic comparison and serialization.
9. Structured diagnostics in S3.
10. Controlled file I/O.

This order supports migration because early compiler candidates need text,
ordered data, named fields, and reusable pure helpers before they need broad
host interaction. It also keeps the first S3 components deterministic and easy
to compare with Python output.

## Criterios de pronto para iniciar o primeiro componente S3

The project is ready to migrate the first real component only when:

- S3 can represent simple compound data;
- S3 can manipulate strings or render simple text;
- S3 can organize code into reusable helper functions;
- there is a way to test S3 programs automatically;
- there is a Python-vs-S3 comparison path;
- IR, Assembly, and diagnostic golden checks continue passing;
- the chosen component has a small input/output contract;
- the Python implementation remains the reference during evaluation.

## Recomendacao final

Before implementing the first compiler component in S3, the next phase should
prioritize:

- minimal strings;
- arrays or vectors;
- records;
- tests for S3 programs;
- formal selection of the first migratable component.

Do not start with the complete parser or complete lexer. The first component
should be small, deterministic, and easy to compare against Python output.
