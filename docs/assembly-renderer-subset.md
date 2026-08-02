# Assembly Renderer Subset Contract

## Purpose

This contract defines the first subset of the S3 Assembly renderer that may be
migrated from Python to S3 in a future delivery.

Python remains the reference implementation. S3 does not implement this
component yet. This document only defines the target behavior, input shape,
output text, fixtures, and comparison strategy needed before an implementation
can start.

## Python reference

The current Python reference is:

- `bootstrap/s3/assembly.py`

The relevant renderer surface is:

- `AssemblyProgram.render`;
- `AssemblyFunction.render`;
- `AssemblyParameter.render`;
- `AssemblyMemoryObject.render`, though memory is not in the initial fixtures;
- `AssemblyBlock.render`;
- `AssemblyInstruction.render`.

The current rendered output is also observed by committed golden artifacts:

- `tests/golden/inspect/*.assembly.txt`

Those goldens are the concrete reference for the initial subset.

## Initial fixtures

Initial source fixtures:

- `examples/first.s3`
- `examples/simple_call.s3`
- `examples/sign.s3`

Corresponding Assembly goldens:

- `tests/golden/inspect/first.assembly.txt`
- `tests/golden/inspect/simple_call.assembly.txt`
- `tests/golden/inspect/sign.assembly.txt`

These fixtures cover a small but useful rendering surface: single and multiple
functions, parameters, registers, labels, calls, arithmetic, comparison,
ternary branching, inversion, constants, returns, source comments, and final
newlines.

## Supported directives in the first subset

The initial subset supports only directives observed in the current Assembly
goldens:

| Directive | Observed form | Notes |
| --- | --- | --- |
| `.s3asm` | `.s3asm 0.6.0` | Must be the first non-empty line and preserve the current version text. |
| `.function` | `.function <name> -> <return_type-group>` | Function order is preserved from input. |
| `.param` | `    .param rN, <type>` | Present in `simple_call` and `sign`; parameter order is preserved. |
| `.register` | `    .register rN, <type>` | Register order is preserved from input. |
| `.label` | `.label <name>` | Block order is preserved from input. |
| `.end` | `.end` | Ends each function body. |

No other directive is part of the first subset. In particular, `.memory` is part
of the Python Assembly model but is not included until a fixture requires it.

## Supported instruction forms in the first subset

The initial subset supports only opcodes and operand forms observed in the
current Assembly goldens:

| Opcode | Observed form | Example |
| --- | --- | --- |
| `TCONST` | destination register and decimal immediate | `    TCONST r0, 10 ; source=2:16:35` |
| `TMOV` | destination register and source register | `    TMOV   r1, r0 ; source=2:5:24` |
| `TINV` | destination register and source register | `    TINV   r4, r3 ; source=4:14:68` |
| `TADD` | destination register and two source registers | `    TADD   r5, r1, r4 ; source=4:14:68` |
| `TCMP` | destination register and two source registers | `    TCMP   r2, r0, r1 ; source=2:17:47` |
| `TCALL` | destination register group, callee name, zero or more argument registers | `    TCALL  r2, add, r0, r1 ; source=5:12:86` |
| `TBR3` | condition register and three labels | `    TBR3   r2, switch_negative_0, switch_neutral_1, switch_positive_2 ; source=2:5:35` |
| `TRET` | source register group | `    TRET   r5 ; source=4:5:59` |

No zero-operand instruction is observed in the initial fixtures.

Every observed instruction line includes a source comment in the form:

```text
; source=<line>:<column>:<offset>
```

The first subset must preserve this comment when the conceptual input includes
a source span. It does not need to invent source spans.

## Formatting contract

The renderer output must follow the Python reference exactly for the supported
subset:

- function order is preserved;
- parameter order is preserved;
- register order is preserved;
- label and instruction order are preserved;
- `.param` and `.register` lines are indented with four spaces;
- instruction lines are indented with four spaces;
- opcodes are left-aligned in a six-character field followed by one space;
- operands use `, ` as the separator;
- source comments use ` ; source=<line>:<column>:<offset>`;
- functions are separated by one blank line;
- `.s3asm 0.6.0` is followed by one blank line before the first function;
- final newline is mandatory;
- output contains no absolute path;
- output contains no host information;
- output contains no timestamp;
- output contains no Python version.

For this subset, text equality is the contract. Formatting normalization should
be avoided unless a future comparison tool explicitly defines it.

## Conceptual input contract

This is a conceptual model for a future S3 implementation, not current S3
syntax.

Ideal future input with records, enums, and arrays:

```text
AssemblyProgram
  version
  functions[]

AssemblyFunction
  name
  return_type
  result_types
  parameters[]
  registers[]
  blocks[]

AssemblyParameter
  register
  type

AssemblyRegister
  register
  type

AssemblyBlock
  label
  instructions[]

AssemblyInstruction
  opcode
  registers[]
  immediate?
  callee?
  labels[]
  source_span?

SourceSpan
  line
  column
  offset
```

Minimum temporary input, if the language cannot express the ideal model yet:

- one fixed program shape per fixture or per small fixture group;
- integer opcode tags instead of enums;
- positional fields instead of records;
- fixed arrays where dynamic vectors are not available;
- source spans represented as simple triples.

Blocking language features:

- strings for names, opcodes, labels, comments, and output text;
- arrays or vectors for ordered functions, registers, blocks, and instructions;
- records or structs for named Assembly data;
- enums or sum types for opcodes and types;
- deterministic formatting helpers;
- reusable functions for repeated line rendering.

## Required S3 language features

| Feature | Priority | Why needed | Temporary workaround |
| --- | --- | --- | --- |
| Strings | P0 | Required to build deterministic Assembly text. | None for a meaningful renderer. |
| Arrays or vectors | P0 | Required to preserve ordered declarations, blocks, and instructions. | Fixed arrays for tiny fixtures only. |
| Reusable functions | P0 | Required for rendering registers, operands, source comments, and lines consistently. | Keep helpers in one file before modules exist. |
| Tests for S3 programs | P0 | Required to validate the renderer as a compiled S3 program. | Existing program check tooling can validate fixture programs. |
| Records or structs | P1 | Required to model Assembly functions, blocks, and instructions clearly. | Positional encodings for early experiments. |
| Enums or sum types | P1 | Required to model opcodes and Assembly types safely. | Integer tags for a small subset. |
| Deterministic formatting helpers | P1 | Required to avoid formatting drift between Python and S3. | Hard-code tiny fixture formatting only as a temporary step. |
| Modules/imports | P1 | Required once renderer helpers are split across files. | Single-file implementation for the first experiment. |

## Comparison strategy

Future comparison should follow this flow:

1. The Python compiler renders reference Assembly using
   `bootstrap/s3/assembly.py`.
2. The future S3 Assembly renderer subset renders candidate Assembly for the
   same conceptual Assembly data.
3. A tool compares the deterministic text output.
4. Differences are reported as a unified diff.
5. CI runs the comparison once the S3 implementation exists.

The initial comparison should use the three committed inspect goldens as the
expected behavior. If future fixture coverage expands, the subset contract
should be updated before the S3 implementation claims support.

## Acceptance criteria

The subset can be considered implemented in S3 only when:

- the S3 component compiles;
- the component covers `first`, `simple_call`, and `sign`;
- output is byte-for-byte identical to the Python renderer for the supported
  subset;
- `tools/s3_program_check.py check` passes;
- `tools/golden_inspect.py check` passes;
- `tools/golden_diagnostics.py check` passes;
- the Python reference remains available;
- CI can validate the Python-vs-S3 comparison.

## Out of scope

The first subset does not include:

- parsing Assembly text;
- broad Assembly validation;
- execution or emulation;
- native backend work;
- every Assembly opcode;
- public CLI changes;
- changing the `.s3asm` format;
- replacing the Python renderer;
- changing existing goldens.
