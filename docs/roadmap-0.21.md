# S3 0.21 Roadmap

Status: closed

## Objective

Add an executable S3 output model for the renderer bootstrap. The model computes
deterministic structural metrics for the current Assembly fixture outputs
without requiring runtime strings, I/O, arrays, or full textual rendering.

## Delivery

S3 0.21 -- S3 renderer bootstrap output model.

The milestone adds
`examples/self_hosting/assembly_renderer_output_model.s3`, a real S3 program
that compiles and runs through the current Python bootstrap toolchain. Its
`main` entrypoint returns `0` when the output-model self-check passes.

The model validates the current fixture metrics derived from the inspect
goldens:

- `first`: 18 lines, 1 function, 0 params, 6 registers, 0 memory objects, 1
  label, 7 instructions, 10 directives, and 5 distinct opcodes;
- `simple_call`: 21 lines, 2 functions, 2 params, 4 registers, 0 memory
  objects, 2 labels, 6 instructions, 13 directives, and 4 distinct opcodes;
- `sign`: 36 lines, 2 functions, 1 param, 9 registers, 0 memory objects, 5
  labels, 14 instructions, 20 directives, and 6 distinct opcodes.

Combined totals are 75 lines, 5 functions, 27 instructions, and 43 directives.
The model also keeps the current supported opcode count at 13 and verifies that
an unknown fixture fails validation.

`tools/s3_program_check.py check` now includes the output model with hosted
expected return `0`. `tools/compare_assembly_renderer.py --candidate-run`
continues to execute the existing stub and bootstrap spike, then also executes
the output model and reports `s3 output model: passed` while the renderer
implementation and full text rendering remain `not_implemented`.

## Non-Goals

This milestone does not implement the full textual S3 Assembly renderer. It
does not implement runtime strings, arrays, heap, stdlib, or I/O. It does not
make `compare --check` pass, alter inspect goldens or candidate actual outputs,
change `AssemblyProgram.render()`, change `render_supported_program()`, or
change parser, lexer, semantic analysis, lowering, IR, optimizer, backend, or
emulator behavior.

`python tools/compare_assembly_renderer.py --candidate-compare-available`
continues to validate the available actual outputs with exit code 0.

`python tools/compare_assembly_renderer.py --check` continues to return exit
code 1 because the real textual S3 Assembly renderer is still not implemented.

## Completion

S3 0.21 is complete as a single output-model block. There is no 0.21-B planned.

The next phase should explicitly choose between:

- evolving the output model toward a segmented textual representation;
- expanding S3 string/text runtime capability enough for real textual rendering.

No 0.22 roadmap is opened by this milestone.
