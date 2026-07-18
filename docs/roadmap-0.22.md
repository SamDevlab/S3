# S3 0.22 Roadmap

Status: closed

## Objective

Add an executable S3 text segment model for the renderer bootstrap. The model
represents textual Assembly renderer pieces as stable numeric IDs without
runtime strings, arrays, I/O, or full textual rendering.

## Delivery

S3 0.22 -- S3 renderer text segment model.

The milestone adds
`examples/self_hosting/assembly_renderer_text_segments.s3`, a real S3 program
that compiles and runs through the current Python bootstrap toolchain. Its
`main` entrypoint returns `0` when the text-segment self-check passes.

The model assigns numeric IDs to the current renderer text segment kinds:
`.s3asm`, `.function`, `.param`, `.register`, `.memory`, `.label`, `.end`,
instruction lines, blank lines, and source metadata markers. The IDs are scalar
`tryte` values, not runtime strings.

The model validates segment metrics derived from the inspect goldens:

- `first`: 18 lines, 25 segments, 10 directive segments, 1 function segment,
  0 param segments, 6 register segments, 0 memory segments, 1 label segment,
  7 instruction segments, 1 blank-line segment, 7 source metadata segments,
  and 1 `.end` segment;
- `simple_call`: 21 lines, 27 segments, 13 directive segments, 2 function
  segments, 2 param segments, 4 register segments, 0 memory segments, 2 label
  segments, 6 instruction segments, 2 blank-line segments, 6 source metadata
  segments, and 2 `.end` segments;
- `sign`: 36 lines, 50 segments, 20 directive segments, 2 function segments,
  1 param segment, 9 register segments, 0 memory segments, 5 label segments,
  14 instruction segments, 2 blank-line segments, 14 source metadata segments,
  and 2 `.end` segments.

Combined totals are 75 lines, 102 segments, 43 directive segments, 27
instruction segments, 8 label segments, 5 blank-line segments, 27 source
metadata segments, and 5 `.end` segments.

`tools/s3_program_check.py check` now includes the text segment model with
hosted expected return `0`. `tools/compare_assembly_renderer.py
--candidate-run` continues to execute the existing stub, bootstrap spike, and
output model, then also executes the text segment model and reports
`s3 text segment model: passed` while the renderer implementation and full text
rendering remain `not_implemented`.

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

S3 0.22 is complete as a single text-segment-model block. There is no 0.22-B
planned.

The next phase should explicitly choose between:

- evolving the segments toward a hosted textual representation;
- expanding S3 string/text runtime capability enough for real textual rendering.

Compare `--check` remains blocked until a real textual S3 renderer exists.
No 0.23 roadmap is opened by this milestone.
