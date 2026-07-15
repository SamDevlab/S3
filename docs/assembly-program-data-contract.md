# AssemblyProgram Data Contract

## Purpose

This document defines the conceptual data structure that a future S3 Assembly
renderer will need to consume.

Python remains the reference implementation. S3 does not implement this
renderer yet. This contract does not change the language, the Assembly format,
or any compiler behavior. Its purpose is to make the future renderer input shape
explicit before implementation starts.

## Relationship to previous contracts

This contract connects the recent planning artifacts:

- `docs/assembly-renderer-subset.md` defines the rendering behavior, initial
  fixtures, formatting rules, and comparison strategy.
- `tests/golden/assembly_renderer_subset_manifest.json` freezes the current
  fixture set, Assembly format version, directives, and opcodes observed in the
  initial renderer subset.
- `docs/array-capabilities.md` records that fixed-size arrays exist, but are
  limited and not first-class values.
- `docs/minimal-string-contract.md` defines the future string capability needed
  for names, directives, comments, separators, and output text.
- `docs/structured-data-capabilities.md` records that records, structs, enums,
  sum types, variants, and general pattern matching are not source-level S3
  features today.

This document turns those inputs into a concrete `AssemblyProgram` data shape
for a later S3 renderer.

## Contract version

Initial data contract version:

```text
assembly_program_data_contract_version: 1.0.0
```

The version must change when fields, operand variants, ordering rules, or
invariants change. It is independent from the current Assembly text format
version, which is still `0.5.0` in the subset manifest.

## Top-level model

Conceptual model:

```text
AssemblyProgram
  assembly_format_version
  functions[]

AssemblyFunction
  name
  return_type
  params[]
  registers[]
  labels[]
  instructions[]

AssemblyRegister
  name
  type

AssemblyLabel
  name

AssemblyInstruction
  opcode
  operands[]
  source?

AssemblyOperand
  kind
  value

AssemblySource
  file?
  line?
  column?
  offset?
  note?
```

This is conceptual data, not required current S3 syntax.

The Python reference currently groups instructions through `AssemblyBlock`
objects in `bootstrap/s3/assembly.py`. This contract keeps labels and
instructions as explicit renderer-facing entities, but a real implementation
must preserve the label-to-instruction partition. It may do that with a future
block-like grouping or with an explicit label range rule.

## Required ordering rules

Order must be preserved for:

- `AssemblyProgram.functions`;
- `AssemblyFunction.params`;
- `AssemblyFunction.registers`;
- `AssemblyFunction.labels`;
- `AssemblyFunction.instructions`;
- `AssemblyInstruction.operands`.

Ordering is part of the observable contract because the renderer is validated
with byte-for-byte Assembly text comparison against committed goldens.

## Field requirements

| Entity | Field | Required | Type concept | Notes |
| --- | --- | --- | --- | --- |
| `AssemblyProgram` | `assembly_format_version` | yes | string | Emits `.s3asm 0.5.0` for the current subset. |
| `AssemblyProgram` | `functions` | yes | ordered array of `AssemblyFunction` | Function order is output order. |
| `AssemblyFunction` | `name` | yes | string | Emits `.function <name> -> <return_type>`. |
| `AssemblyFunction` | `return_type` | yes | Assembly type tag | Current subset uses `trit` and `tryte`. |
| `AssemblyFunction` | `params` | yes | ordered array of `AssemblyRegister` | Emits `.param` lines before `.register` lines. |
| `AssemblyFunction` | `registers` | yes | ordered array of `AssemblyRegister` | Emits `.register` lines. |
| `AssemblyFunction` | `labels` | yes | ordered array of `AssemblyLabel` | Emits `.label` lines. |
| `AssemblyFunction` | `instructions` | yes | ordered array of `AssemblyInstruction` | Instruction order must match label partitions. |
| `AssemblyRegister` | `name` | yes | string | Current rendered form is `rN`. |
| `AssemblyRegister` | `type` | yes | Assembly type tag | Current values are `trit` or `tryte`. |
| `AssemblyLabel` | `name` | yes | string | Current labels include `entry` and generated switch labels. |
| `AssemblyInstruction` | `opcode` | yes | opcode tag | Must be one of the supported subset opcodes. |
| `AssemblyInstruction` | `operands` | yes | ordered array of `AssemblyOperand` | Operand order is textual order. |
| `AssemblyInstruction` | `source` | no | optional `AssemblySource` | Current goldens include source comments, but the Python model allows missing source metadata. |
| `AssemblyOperand` | `kind` | yes | operand kind tag | Distinguishes registers, constants, labels, functions, and types. |
| `AssemblyOperand` | `value` | yes | tag-specific scalar | Value interpretation depends on `kind`. |
| `AssemblySource` | `file` | no | string | Not emitted by the current subset. |
| `AssemblySource` | `line` | yes, if source is present | integer | Current comment uses `source=<line>:<column>:<offset>`. |
| `AssemblySource` | `column` | yes, if source is present | integer | Current comment uses `source=<line>:<column>:<offset>`. |
| `AssemblySource` | `offset` | yes, if source is present | integer | Required by current source comments. |
| `AssemblySource` | `note` | no | string | Not emitted by the current subset. |

## Operand variants

Required first, derived from the current subset and goldens:

| Operand kind | Required first | Used by | Notes |
| --- | --- | --- | --- |
| `register` | yes | `TADD`, `TCALL`, `TCMP`, `TCONST`, `TINV`, `TMOV`, `TRET`, `TBR3` | Rendered as `rN`. |
| `constant` | yes | `TCONST` | Rendered as a decimal immediate. |
| `label` | yes | `TBR3` | Rendered as a label name. |
| `function` | yes | `TCALL` | Rendered as the callee function name. |
| `type` | yes | `.function`, `.param`, `.register` | Needed for function return and register declarations. |

Useful later:

| Operand kind | Required first | Why later |
| --- | --- | --- |
| `memory` | no | The current renderer subset manifest does not include `.memory`, `TLOAD`, or `TSTORE`. |
| `none` | no | No zero-operand instruction appears in the initial fixtures. |

## Opcode coverage

The current subset manifest lists these opcodes:

- `TADD`
- `TBR3`
- `TCALL`
- `TCMP`
- `TCONST`
- `TINV`
- `TMOV`
- `TRET`

| Opcode | Operand shape | Fixtures | Notes |
| --- | --- | --- | --- |
| `TADD` | destination register, left register, right register | `first`, `simple_call` | Arithmetic instruction with three register operands. |
| `TBR3` | condition register, negative label, neutral label, positive label | `sign` | Preserves ternary branch label order. |
| `TCALL` | destination register, function name, zero or more argument registers | `simple_call`, `sign` | The callee is a function-name operand, not a register. |
| `TCMP` | destination register, left register, right register | `sign` | Produces a trit result in the observed fixture. |
| `TCONST` | destination register, decimal immediate | `first`, `simple_call`, `sign` | Immediate values are scalar constants. |
| `TINV` | destination register, source register | `first`, `sign` | Unary register operation. |
| `TMOV` | destination register, source register | `first` | Register copy. |
| `TRET` | source register | `first`, `simple_call`, `sign` | Terminates a function path. |

## Directive coverage

The current subset manifest lists these directives:

- `.end`
- `.function`
- `.label`
- `.param`
- `.register`
- `.s3asm`

| Directive | Contract source | Notes |
| --- | --- | --- |
| `.s3asm` | `AssemblyProgram.assembly_format_version` | Emits the Assembly text format version. |
| `.function` | `AssemblyFunction` | Uses `name` and `return_type`. |
| `.param` | `AssemblyFunction.params` | Emitted in parameter order. |
| `.register` | `AssemblyFunction.registers` | Emitted in register declaration order. |
| `.label` | `AssemblyFunction.labels` | Must preserve the label-to-instruction partition. |
| `.end` | `AssemblyFunction` end marker | No separate data payload is needed for the current subset. |

## Mapping to S3 language capabilities

| Contract feature | Needs strings | Needs arrays | Needs records | Needs enums or sum types | Possible with current S3 | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Names | yes | no | no | no | no | Runtime strings do not exist yet. |
| Ordered functions | no | yes | yes | no | partially | Current arrays can model small fixed lists but are not first-class. |
| Ordered params/registers/labels | yes | yes | yes | yes | partially | Names and type tags need future support. |
| Instruction shape | no | yes | yes | yes | no | Positional arrays alone lose field meaning. |
| Operand variants | yes | yes | yes | yes | no | Needs safe tags or a future variant model. |
| Opcode dispatch | no | no | no | yes | partially | Numeric tags could prototype a tiny subset. |
| Source metadata | no | no | yes | no | partially | Line, column, and offset are scalar, but named grouping is missing. |
| Deterministic output | yes | yes | no | no | no | Formatting helpers and output text support are still missing. |

## Minimal prototype path

This is a future implementation route, not work done in this delivery:

1. Represent opcodes as numeric tags.
2. Represent operand kinds as numeric tags.
3. Use fixed arrays for tiny ordered lists where current array restrictions
   permit it.
4. Use a static table of future string literals for names, labels, directives,
   and opcode text.
5. Add records, enums, or an explicit tag-plus-fields representation.
6. Use this contract to feed the future S3 renderer subset.

This route can prove a narrow path, but it should not become the long-term
structured data model without explicit invariants.

## Blockers

Remaining blockers:

- string runtime or a safe static string table;
- records, structs, or an equivalent named-field representation;
- enum, sum type, or safe tagged representation;
- first-class arrays or a controlled alternative for ordered contract data;
- deterministic formatting helpers;
- automated Python-vs-S3 renderer comparison;
- renderer harness that can exercise the three initial fixtures.

## Acceptance criteria

This contract is ready to support implementation when:

- each entity has a representable S3 form;
- minimal strings exist or a safe static table exists;
- ordered lists are representable;
- instruction operands are representable without ambiguity;
- the S3 renderer produces the same text for `first`, `simple_call`, and
  `sign`;
- byte-for-byte comparison is automated;
- existing goldens continue to pass.

## Out of scope

This contract does not:

- implement the renderer;
- change the Assembly format;
- change IR;
- change any backend;
- support every opcode;
- support every type;
- execute Assembly;
- replace the Python renderer.

## Next recommendations

0.10-M:
Create a Python-vs-S3 renderer comparison harness with a placeholder S3
component, without implementing the renderer yet.

0.10-N:
Choose the first real implementation target: minimal string type support or a
tagged record/operand representation.

These are planning recommendations, not implementation commitments.
