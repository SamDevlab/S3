# S3 AI Agent Guide

S3 is AI-first and human-auditable.

This document provides clear, verifiable guidance for artificial intelligence agents interacting with the S3 programming language toolchain. It defines the supported language subset, toolchain capabilities, error repair patterns, and execution boundaries.

## Purpose

The primary intended user of the S3 toolchain is an AI agent generating, inspecting, compiling, diagnosing, repairing, and testing S3 source code and intermediate representations, while keeping all artifacts transparent and audit-verifiable by human engineers.

## Intended agent workflow

1. **Read & Discover Capabilities**: Query `docs/ai-capabilities.json` or run `s3 doctor` to check toolchain versions and supported feature limits.
2. **Author Code**: Write S3 code using V0.6 syntax only (the default). Rely on explicit typing (`trit`, `tryte`, `string`, enums, records, fixed arrays) and explicit mutability (`mut`).
3. **Compile & Check**: Run `s3 check <file.s3>` or `s3 inspect <file.s3> --emit ir` to validate syntax and semantics.
4. **Interpret Diagnostics**: If checking fails, parse JSON diagnostics via `s3 check --diagnostic-format json` or textual diagnostics.
5. **Repair Loop**: Fix errors guided by precise diagnostic codes and line/column locations without inventing non-existent features.
6. **Execute & Test**: Run programs using `s3 run <file.s3>` (emulator) or run differential test suites.

## Supported language subset

- **Scalar Types**: `trit` (-1, 0, 1), `tryte` (-364 to +364 / 9 trits), signed `i64`, and `f64`; integer overflow is checked.
- **Static Text**: Static `string` literals, compile-time static text evaluation (`len`, concatenation, equality, slicing, indexing). Text values in records/payloads are fixed scalar handles.
- **Fixed Arrays**: Static 1D arrays of `trit`/`tryte` with constant bounds. Static `len(arr)` expressions.
- **Records**: Nominal struct types (`record Name { field: Type }`), depth-first scalar leaf layout. Local, imported, and acyclic nested records.
- **Enums**: Nominal enums (`enum Name { Variant }` or tag-first payload enums `Variant(Type)`), exhaustive `match` expressions.
- **Control Flow**: `if`/`else`, `while`, `for` loops, `break`, `continue`, tail calls, recursion, and functions.
- **Modules**: Multi-file deterministic compilation with `module name;`, `from mod import sym;`, and `export fn`.
- **Optimization**: O0 (default) and O1 (SSA optimizations including SCCP, DCE, GVN, DSE, and Memory SSA). The 1.4 campaign candidate additionally evaluates conservative loop/range proofs and BCE; branch-only status is recorded in `docs/ai-capabilities.json`.
- **Scientific library**: `s3.v1.science` is integrated. The 1.4 candidate branch adds `s3.v1.geometry`; candidate APIs are not part of `main` until merged.
- **Typed references**: `&T`, `&mut T`, and bounded borrowed slices are supported in their documented contexts. These are typed references, not raw pointers; raw pointer arithmetic and reference/integer casts are unsupported.
- **Closed generic collections**: `map<i64, i64>`, `map<text, i64>`, and `set<i64>` use explicit deterministic specializations; this is not open-ended type erasure.
- **Compiler substrate V1**: hosted deterministic text-keyed maps, symbol interning, direct-ID arenas, lexical environment state, source bundle/cursors, and bounded transactional output are available as substrate contracts. They do not constitute a self-hosted compiler.
- **Generic syntax/IR substrate**: a flat indexed `SyntaxArena`, an arena-backed generic IR program, a transactional IR builder, and an independent structured verifier are available as hosted V1 contracts. They do not implement parsing, lowering, emission, or self-hosting.
- **Whole-program control plane**: `ProgramRegistry`, canonical transactional `TypeArena`, explicit `SemanticState`, bounded diagnostic state, deterministic phase orchestration, and `WholeProgramContext` are available for prepared-artifact composition. This control plane does not parse source or emit output; `compile_program` fails closed without `TEST_ARTIFACT_INPUT`.

## Unsupported features

- No raw or unbounded host heap access; owned runtime collections use explicit bounded allocation APIs.
- No raw pointers, pointer arithmetic, or reference/integer casts. The source-level `&value` and `&mut value` forms create typed references and are distinct from raw pointers.
- No dynamic arrays or resizing lists.
- No dynamic text construction or runtime string parsing.
- No cyclic or self-referential record layouts.
- No open-ended runtime generics, templates, traits, or interfaces. Closed collection specializations are explicit and deterministic.
- No exceptions, unwinding, implicit try/catch, or `?` operator.
- No concurrency, async, threads, or global mutable state.
- No standard C library or external dependency runtimes.

## Stable commands

- `s3 targets`: List supported compile target backends.
- `s3 doctor`: Display toolchain component status and version manifest.
- `s3 check <file.s3>`: Perform syntax and semantic analysis without executing.
- `s3 inspect <file.s3> --emit <summary|ir|assembly>`: Inspect compiler intermediate stages.
- `s3 ir <file.s3>`: Output SSA IR text.
- `s3 ir-json <file.s3> -o <out.json>`: Output canonical JSON IR 0.6.0.
- `s3 asm <file.s3> [-O1]`: Output S3 Assembly 0.6.0.
- `s3 run <file.s3> [--max-instructions N]`: Execute program via hosted emulator.
- `s3 native-asm <file.s3> [-o <out.s>]`: Emit Linux x86-64 GNU assembly.
- `s3 build <file.s3> [-o <bin>]`: Compile standalone Linux x86-64 ELF binary.

## Compile loop

Agents should compile programs step-by-step:
```bash
s3 check path/to/program.s3
```
If clean, generate Assembly or IR:
```bash
s3 asm path/to/program.s3 -O1
```

## Test loop

Agents should verify correctness by executing tests with `pytest`:
```bash
python -m pytest -q
```
For quick feedback on core compiler components, execute targeted test files:
```bash
python -m pytest tests/test_ai_authoring_contract.py -v
```

## Diagnostic repair loop

When compilation produces an error, parse the diagnostic code and span:
- Structured JSON diagnostic outputs code (e.g. `S3C_TYPE_MISMATCH`, `S3C_UNKNOWN_SYMBOL`), line, column, and error explanation.
- **Rule**: Repair only the targeted syntax or semantic violation. Do not add speculative language constructs (like `PHI`, `SUB`, or heap pointers) that do not exist in S3.

## Optimization modes

- `-O0`: Uses the baseline optimizer pipeline. Default for predictable step-by-step debugging.
- `-O1`: Applies semantics-preserving SSA optimizations. In the 1.4 candidate, canonical counted-loop facts may prove selected immutable-vector accesses safe; otherwise runtime bounds checks remain. Proof does not weaken language-level checked indexing.
- Scalar reduction recognition in the 1.4 candidate is metadata-only and ordered. It does not enable floating-point reassociation, fast-math, or SIMD.
- `PER_INSTRUCTION` remains the native instruction-budget default. `EXACT_SEGMENT` and `LOOP_HYBRID` are explicit modes.

## Emulator versus native

- **Emulator (Hosted)**: In-process execution within Python reference implementation. Fully supported on Windows, Linux, and macOS. Default for functional testing.
- **Native Backend (Linux x86-64)**: Emits raw x86-64 assembly and links zero-dependency ELF binaries. Execution requires a Linux environment (e.g. GitHub Actions CI). Windows execution is not supported locally.

## IR and Assembly versions

- **S3 IR JSON**: Version `0.6.0` (Canonical SSA representation).
- **S3 Assembly**: `.s3asm 0.6.0` (Versioned textual assembly).
- Readers maintain backward compatibility for `0.5.0` width-1 artifacts.

## Determinism expectations

- Code generation, symbol ordering, IR output, and Assembly emission are strictly deterministic across runs given the same toolchain version and source code.
- File ordering in multi-module compilation does not affect generated code binary layout.

## Capability discovery

Agents can inspect toolchain capabilities programmatically by reading `docs/ai-capabilities.json` or running `s3 doctor`.

## Common invalid assumptions

- **DO NOT** assume S3 has unsigned integers (e.g., `uint32`).
- **DO NOT** assume S3 has string concatenation at runtime for dynamic input.
- **DO NOT** confuse typed `&T` / `&mut T` references with raw pointers.
- **DO NOT** assume branch-only S3 1.4 optimizer or geometry capabilities are already in `main`.
- **DO NOT** use C-style casting `(int)x`. Use ternary conversion functions or explicit match patterns.
- **DO NOT** assume Windows can run native ELF binaries directly without Linux CI.

## Safe automation boundaries

- Automated AI pipelines may generate `.s3` source files, run `s3 check`, `s3 asm`, `s3 run`, and execute tests.
- Automated AI pipelines MUST NOT modify core operating system settings, install hypervisors, or alter toolchain delivery commitments without explicit human review.

## Human audit requirements

- All AI-generated S3 code, diagnostic fixes, and architecture proposals must remain human-readable, verifiable via automated tests, and documented with clear evidence rules.
