# S3 Self-Hosting Plan

This document describes a practical path for migrating parts of the S3 compiler
from Python to S3. It is not an implementation plan for immediate full
self-hosting. The current Python compiler remains the reference implementation
and bootstrap compiler while the S3 language grows the features needed to host
compiler components safely.

## Estado atual

The current S3 compiler is written in Python. S3 is not self-hosted today: S3
programs are compiled by the Python implementation, and the Python pipeline is
the source of truth for syntax, semantics, IR, Assembly, execution behavior, and
diagnostics.

S3 0.10 is closed as a preparation milestone for self-hosting and the Assembly
renderer candidate. S3 0.11 is closed after deterministic static text
foundation work. S3 0.12 is closed after the first passed actual output for
`first`. S3 0.13 is closed after `simple_call` became available and passed. S3
0.14 is closed after `sign` became available and passed. S3 0.15 is closed
after clarifying that `--candidate-compare-available` validates the passed
actual outputs while the global `compare --check` remains blocked because the
real S3 renderer is still not implemented; see `docs/roadmap-0.10.md`,
`docs/roadmap-0.11.md`, `docs/roadmap-0.12.md`, `docs/roadmap-0.13.md`,
`docs/roadmap-0.14.md`, and `docs/roadmap-0.15.md`. S3 0.16 is open after
starting a minimal Python renderer core for the `first` and `simple_call`
fixture paths; see `docs/roadmap-0.16.md`. This core is an incremental bridge
toward renderer generalization, not a migrated S3 renderer.

Recent tools make this pipeline more observable:

- `s3 targets` lists internal target and backend names.
- `s3 doctor` reports the local compiler environment.
- `s3 check <source.s3>` validates that a source file compiles.
- `s3 inspect <source.s3>` reports compilation summary data.
- `s3 inspect <source.s3> --emit ir` prints compiler IR.
- `s3 inspect <source.s3> --emit assembly` prints S3 Assembly.
- `tools/golden_inspect.py` compares canonical IR and Assembly outputs.
- `tools/golden_diagnostics.py` compares canonical diagnostic outputs.

These tools do not make S3 self-hosted by themselves. They provide comparison
points so a future S3 implementation of a compiler component can be checked
against the Python implementation.

The migration must be incremental. Replacing the full compiler at once would
make regressions hard to isolate and would require language features that do not
exist yet.

## Objetivo de self-hosting

The realistic goal is to write compiler components in S3, compile those S3
components with the current Python compiler, and compare their output or
behavior against the Python reference implementation.

The bootstrap model is:

1. Python remains the compiler used to compile S3 programs.
2. A small compiler component is rewritten in S3.
3. The Python compiler compiles that S3 component.
4. A harness compares the S3 component with the Python component.
5. Passing components can be used experimentally.
6. Only after sustained validation should a component become the default path.

Partial self-hosting comes first. Full self-hosting is a later goal, after S3 can
express and validate larger compiler subsystems.

## Componentes atuais do compilador

| Component | File or area | Responsibility | Migration difficulty | Language dependencies | Recommended phase | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Lexer | `bootstrap/s3/lexer.py` | Convert source text into tokens with source locations. | high | strings, character iteration, diagnostics, source spans | later | Tokenization depends heavily on text handling and precise errors. |
| Parser | `bootstrap/s3/parser.py` | Build AST from tokens and enforce grammar shape. | very high | tokens, recursive data, diagnostics, pattern matching, modules | much later | Too coupled to syntax and errors to migrate first. |
| AST model | `bootstrap/s3/ast.py` | Represent source-level program structure. | medium | records, enums, arrays, comparison helpers | middle | A partial S3 mirror may be useful before a full parser migration. |
| Diagnostics | `bootstrap/s3/diagnostics.py` | Provide structured errors, categories, phases, and JSON shape. | high | records, enums, strings, serialization, source spans | middle | Must remain stable for tooling. |
| Semantic analysis | `bootstrap/s3/semantic.py` | Validate names, types, mutability, and semantic constraints. | high | maps, records, diagnostics, arrays, structured errors | later | Depends on AST and a richer standard library. |
| Lowering | `bootstrap/s3/lowering.py` | Convert AST and semantic data into IR. | high | AST, IR records, arrays, diagnostics | later | Should wait until IR representation is available in S3. |
| IR model | `bootstrap/s3/ir.py` | Represent typed block-based IR. | medium | records, enums, arrays, deterministic rendering | middle | A subset can be represented early for comparison tools. |
| IR verifier and serialization | `bootstrap/s3/ir_verifier.py`, `bootstrap/s3/ir_serialization.py` | Validate IR and read/write canonical IR artifacts. | high | structured errors, JSON-like serialization, maps, arrays | later | Serialization needs deterministic output. |
| Optimizer | `bootstrap/s3/optimizer.py`, `bootstrap/s3/passes.py` | Apply O0/O1 optimization passes while preserving behavior. | very high | IR mutation strategy, dataflow, verification, tests | much later | High regression risk; not an early migration target. |
| Assembly model and parser | `bootstrap/s3/assembly.py` | Represent, render, and parse S3 Assembly. | medium | records, enums, arrays, strings, formatting | earlier | Rendering is a good early candidate; parsing is harder. |
| Codegen | `bootstrap/s3/codegen.py` | Convert IR into S3 Assembly. | high | IR, Assembly records, diagnostics, deterministic output | later | Should wait until both IR and Assembly models are stable in S3. |
| Emulator | `bootstrap/s3/emulator.py` | Execute S3 Assembly with frames, memory, and runtime errors. | very high | maps, arrays, runtime state, structured errors | much later | Broad behavior surface and many observable failures. |
| Native backend | `bootstrap/s3/backends/x86_64/` | Emit native x86-64 assembly and enforce native runtime contracts. | very high | strings, layout data, target contracts, host integration | last | Too platform-specific for early migration. |
| Backend registry and targets | `bootstrap/s3/backends/`, `bootstrap/s3/targets.py` | Keep internal backend and target contracts explicit. | medium | records, enums, modules | middle | Small contracts may be mirrored in S3 later. |
| Pipeline and context | `bootstrap/s3/pipeline.py`, `bootstrap/s3/compilation_context.py` | Orchestrate frontend, IR, optimization, and Assembly generation. | high | all compiler stages, configuration records | later | Should remain Python until component boundaries are proven. |
| CLI | `bootstrap/s3/cli.py` | Expose compiler commands and diagnostics to users. | high | file I/O, arguments, diagnostics, host integration | later | Not a first target because it depends on platform behavior. |
| Golden tools | `tools/golden_inspect.py`, `tools/golden_diagnostics.py` | Compare canonical outputs for regression detection. | low | deterministic output, file I/O, diffing | earlier | Keep Python initially; later a S3 comparator can be tested beside it. |

## Recursos que S3 precisa antes de substituir Python

| Resource | Why it is needed | Depends on it | Priority |
| --- | --- | --- | --- |
| Strings | Source text, names, diagnostics, rendered artifacts, and file content are all text-heavy. | lexer, parser, diagnostics, Assembly renderer | P0 |
| Arrays or vectors | Compiler data is ordered: tokens, AST children, blocks, instructions, registers, and diagnostics notes. | every component | P0 |
| Reusable helper functions | Small pure components need shared formatting, normalization, and comparison helpers. | early helpers, renderers, checkers | P0 |
| Deterministic execution | Python and S3 implementations must produce repeatable output for the same input. | all comparison harnesses | P0 |
| Program tests for S3 code | Migrated components need direct automated tests, not only end-to-end compiler tests. | all migrated components | P0 |
| Structured records | Compiler entities need named fields rather than positional encodings. | AST, IR, Assembly, diagnostics | P1 |
| Enums or sum types | Tokens, opcodes, types, diagnostic categories, and AST variants need closed alternatives. | lexer, parser, IR, Assembly, diagnostics | P1 |
| Stable pattern matching | Component code needs clear branching over syntax and intermediate forms. | parser, lowering, verifier, optimizer | P1 |
| Modules and imports | Compiler code must be split into reusable files with stable boundaries. | any multi-file component | P1 |
| Minimal standard library | Common operations should not be reimplemented inside every compiler component. | all non-trivial S3 components | P1 |
| Structured error handling | Migrated components must report failures without ad hoc sentinel values. | diagnostics, parser, verifier, emulator | P1 |
| Structured diagnostics | Error category, phase, code, location, and notes must remain comparable with Python. | parser, semantic analysis, verifier, runtime checks | P1 |
| Deterministic serialization | IR, Assembly, and diagnostics need canonical artifacts for golden comparison. | golden tools, comparison harnesses | P1 |
| Structural comparison | Python-vs-S3 checks need exact equality over nested compiler data. | comparison harnesses, tests | P1 |
| File reading | A S3 component eventually needs to read source, artifacts, or golden inputs. | CLI-like tools, artifact checkers | P2 |
| File writing | Update tools and generated artifacts need controlled output. | future golden update tools | P2 |
| Host tool integration | Later stages need a narrow way to call or coordinate host-side tools. | experimental adoption, CI harnesses | P2 |

P0 items are needed before the first real migration. P1 items are needed before
migrating larger compiler components. P2 items are needed for broader
self-hosting and tooling adoption.

## Ordem recomendada de migracao

### Phase 1: small S3 programs and pure libraries

- Add richer S3 examples that exercise deterministic computation.
- Stabilize pure helper functions.
- Validate generated IR and Assembly with golden artifacts.
- Keep Python as the compiler and reference.

### Phase 2: deterministic helpers

- Implement small renderers or normalizers in S3.
- Prefer logic with no file I/O and no platform behavior.
- Compare text output against Python helpers.

### Phase 3: simple intermediate structures

- Represent small slices of IR or Assembly in S3.
- Start with records or enum-like encodings once the language supports them.
- Compare JSON or textual golden output generated by Python.

### Phase 4: first real compiler component in S3

Choose a component with a narrow and deterministic surface. Good candidates:

- a simple Assembly renderer;
- an IR normalizer;
- a diagnostic formatter;
- a small static checker.

Do not start with the full lexer or parser. Rendering and normalization are
easier to validate because they can be compared byte-for-byte.

### Phase 5: Python vs S3 comparison

- Generate reference output with the Python component.
- Generate candidate output with the S3 component.
- Compare deterministic artifacts with readable diffs.
- Keep golden artifacts as regression checks.

### Phase 6: larger components

Only after the language and harness are strong enough, consider larger
subsystems:

- lexer;
- parser;
- optimizer;
- backend.

These components require richer language support and stronger diagnostics before
they can be migrated safely.

## O que nao migrar primeiro

Do not begin with:

- the full parser;
- the full lexer;
- the whole optimizer;
- the native backend;
- the full emulator;
- the entire CLI;
- broad file-system behavior;
- platform integration.

These areas have high coupling, depend on many missing language features, and
are hard to validate without prior comparison infrastructure. Starting there
would make the compiler harder to trust while the language is still growing.

## Criterios para considerar um componente migrado

A component can be considered migrated only when:

- there is an implementation in S3;
- the Python implementation remains available as a reference;
- there is automatic comparison between Python and S3 behavior;
- inspect and diagnostic golden checks still pass;
- compatible errors are reported for invalid inputs;
- output is deterministic;
- CI validates the comparison path;
- the component has a small and clear scope;
- adoption can be rolled back without changing language semantics.

Experimental use is not the same as migration. A component should become the
default only after the comparison path stays stable over time.

## Estrategia bootstrap

The initial bootstrap flow is:

1. The Python compiler compiles S3 programs.
2. One compiler component is rewritten in S3.
3. The Python compiler compiles that S3 component.
4. A tool compares Python output against S3 output.
5. If the comparison passes, the S3 component can be used experimentally.
6. After repeated validation, the S3 component may become the default path.

Python will remain the bootstrap compiler for a long time. S3 should replace
Python one component at a time, with partial self-hosting before any attempt at
complete self-hosting.
