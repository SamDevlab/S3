# Milestone 1.01 - First Self-hosting Component

## Goal

Implement a small, pure, deterministic S3 component from the toolchain and
validate it against a Python reference without replacing the Python compiler
path.

## Selected Component

The selected component is the Assembly opcode classifier.

It is a narrow subcomponent of the Assembly renderer subset. It classifies the
current `AssemblyOpcode` inventory into deterministic scalar metadata:

- known opcode id;
- opcode kind code;
- minimum textual operand count;
- variadic operand-count flag;
- operand-count acceptance.

The Python reference remains `bootstrap/s3/assembly.py`, specifically the
`AssemblyOpcode` inventory and parse-time operand-count contract.

## S3 Implementation

The S3 implementation lives under `selfhost/assembly/`:

- `opcode_ids.s3` provides stable scalar ids for the current Assembly opcode
  inventory;
- `opcode_classifier.s3` uses modules, records, enums, and exhaustive enum
  matching to classify opcodes.

The public S3 comparison entry points remain scalar because type imports and
runtime strings are not part of this milestone. Internally, the classifier uses:

- `AssemblyOpcode` enum;
- `OpcodeKind` enum;
- `OpcodeQuery` record;
- exhaustive `match` over every opcode variant.

## Differential Validation

`tests/test_self_hosting_opcode_classifier.py` compares Python and S3 behavior
for:

- every current Assembly opcode variant;
- valid minimum operand counts;
- invalid opcode ids;
- fixed-count and variadic `TCALL` operand behavior;
- deterministic multi-file compilation order;
- native x86-64 checksum execution when the native toolchain is available.

Local Windows validation collects the native checksum test and skips it when the
Linux x86-64 native toolchain is unavailable.

## Maturity

Status: `differential reference`.

The component is not adopted by the compiler runtime. Python remains the
reference and default implementation. Adoption would require a later milestone
with sustained CI history and a deliberate integration point.

## Non-goals

- no full Assembly text renderer;
- no parser, lexer, optimizer, emulator, backend, or CLI migration;
- no runtime strings;
- no file I/O in S3;
- no type imports;
- no default-path replacement;
- no tag, release, or public version bump.
