# Array and Vector Capability Inventory

## Purpose

Arrays do not need to be reserved in S3: the language already has fixed-size
array syntax, AST nodes, semantic checks, lowering, and execution coverage.

This inventory records the current capability so self-hosting planning can
distinguish between an absent feature and a feature that exists but may still be
too narrow for future compiler components.

## Current Syntax

Observed array syntax:

- array type: `tryte[3]`
- array literal: `[1, 2, 3]`
- indexing: `values[0]`
- mutable element assignment: `values[1] = 4`

Examples already exist in:

- `examples/static_array.s3`
- `examples/trit_array.s3`
- `tests/test_parser_arrays_v0_6.py`
- `tests/test_memory_frontend.py`

There is no separate vector syntax today. The current feature is fixed-size
arrays indexed by tryte-compatible expressions.

## Implementation Map

| Layer | File/area | Current support | Notes |
| --- | --- | --- | --- |
| Lexer | `bootstrap/s3/lexer.py` | `LEFT_BRACKET`, `RIGHT_BRACKET`, and `COMMA` tokens | Brackets also participate in indentation/newline suppression while inside delimiters. |
| Parser | `bootstrap/s3/parser.py` | Parses array types, array literals, indexing, and indexed assignment | Array literals are accepted as initializers, not general scalar expressions. |
| AST | `bootstrap/s3/ast.py` | `ArrayType`, `ArrayLiteral`, `IndexExpression`, and `IndexTarget` | `ArrayLiteral` is part of `Initializer`, while array element reads are expressions. |
| Semantic analysis | `bootstrap/s3/semantic.py` | Validates lengths, element types, mutability, index type, and constant bounds | Rejects nested arrays, arrays in signatures, whole-array assignment, and scalar use of arrays. |
| Lowering | `bootstrap/s3/lowering.py` | Lowers arrays to IR memory objects with `LOAD` and `STORE` | Array declarations allocate memory and initialize each element. |
| IR | `bootstrap/s3/ir.py` | Represents lowered arrays as memory objects and memory instructions | Arrays are not first-class IR values. |
| Assembly | `bootstrap/s3/codegen.py`, `bootstrap/s3/assembly.py` | Emits memory declarations and `TLOAD`/`TSTORE` | Assembly sees memory, not source-level arrays. |
| Runtime/emulator | `bootstrap/s3/emulator.py` | Executes memory load/store with bounds, initialization, mutability, and memory-budget checks | Dynamic out-of-bounds access is a runtime diagnostic. |
| Native backend | `bootstrap/s3/backends/x86_64/` | Supports memory layout and `TLOAD`/`TSTORE` in native emission | Covered by native integration tests when Linux x86-64 is available. |
| Tests | `tests/test_parser_arrays_v0_6.py`, `tests/test_memory_frontend.py`, `tests/test_memory_lowering.py`, `tests/test_native_x86_64_integration.py` | Covers parsing, semantic validation, lowering, hosted execution, and native differential cases | Native tests are skipped on hosts that cannot build Linux x86-64 binaries. |
| Diagnostics | `tests/golden/diagnostics/static_bounds.s3` | Covers one array-related semantic diagnostic through golden diagnostics | Other array diagnostics are primarily asserted in focused tests. |

## Existing Tests

- `tests/test_parser_arrays_v0_6.py`: v0.5/v0.6 AST parity, multiline
  literals, literal expressions, arrays in `match`, recursion/frame isolation,
  syntax failures, semantic failures, and dynamic hosted bounds.
- `tests/test_memory_frontend.py`: lexer tokens, AST node construction, call
  and indexing precedence, semantic validation, length limits, element typing,
  constant bounds, immutability, rejected array signatures, rejected nested
  arrays, and rejected whole-array assignment.
- `tests/test_memory_lowering.py`: memory lowering for mutable scalars and
  arrays, including declared memory length and initialization stores.
- `tests/test_cli_source_syntax.py`: CLI-level v0.6 execution and artifact
  parity for array syntax.
- `tests/test_native_x86_64_integration.py`: native differential cases for
  array reads, writes, and bounds when the native environment is available.
- `tests/golden/diagnostics/static_bounds.s3`: deterministic diagnostic output
  for a compile-time array bounds failure.

## Supported Behavior

- Fixed-size array types: confirmed by tests.
- `trit` and `tryte` element arrays: confirmed by tests.
- Array literals in declarations: confirmed by tests.
- Multiline array literals: confirmed by tests.
- Literal elements that are expressions or calls: confirmed by tests.
- Index expressions such as `values[1]`: confirmed by tests.
- Mutable element assignment: confirmed by tests.
- Immutable arrays rejecting element writes: confirmed by tests.
- Static length validation: confirmed by tests.
- Constant index bounds checks: confirmed by tests.
- Dynamic index bounds checks in hosted execution: confirmed by tests.
- Lowering to memory objects and `LOAD`/`STORE`: confirmed by tests.
- Native execution of array memory operations: confirmed by tests where the
  native target is available.

## Known Limitations

- Arrays are fixed-size only; no vector growth or dynamic length is visible.
- Array lengths must be positive and cannot exceed the tryte-indexed maximum
  of 365 elements.
- Empty literals parse, but a valid array declaration cannot currently use a
  zero-length array because nonpositive lengths are rejected.
- Nested arrays are rejected.
- Arrays cannot be function parameters.
- Functions cannot return arrays.
- Whole-array assignment is rejected.
- Arrays cannot be passed as arguments.
- Arrays cannot be used as scalar values or operator operands.
- Structural array comparison is not supported.
- Source-level arrays lower to memory, so they are not first-class IR values.
- Deterministic serialization of source-level array values is not defined.
- Arrays of future records or strings cannot be assessed until those features
  exist.

## Relevance For Self-Hosting

Arrays can help a future Assembly renderer subset represent ordered collections
such as:

- functions;
- registers;
- labels;
- instructions;
- operands.

The current support is useful but not sufficient by itself. A renderer-like S3
component still needs:

- real strings or string buffers for names, labels, opcodes, comments, and
  output text;
- records or structs for functions, blocks, instructions, and source spans;
- enums or sum types for opcodes and Assembly types;
- deterministic formatting helpers;
- modules/imports once helpers stop fitting comfortably in one file;
- deterministic serialization or comparison tools for renderer output.

## Impact On Roadmap

Arrays/vectors are not a total absence gap. The current gap is whether the
existing fixed-size array support is sufficient and ergonomic enough for real
compiler components.

Strings remain the stronger blocker for the Assembly renderer subset because
rendering is fundamentally text-producing. Records and enums are also likely
needed before instruction-like data can be represented clearly.

## Next Recommendations

- 0.10-J: define minimal real string semantics or string buffers.
- 0.10-K: inventory records/structs, or define a temporary representation for
  instruction-like data.
- 0.10-L: create an AssemblyProgram data contract using existing language
  capabilities and explicitly documented gaps.
