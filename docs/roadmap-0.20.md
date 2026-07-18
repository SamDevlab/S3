# S3 0.20 Roadmap

Status: closed

## Objective

Create the first executable S3 artifact for the future Assembly renderer. This
bootstrap spike validates real supported-subset invariants while avoiding full
text rendering, because S3 still lacks the runtime string and I/O support needed
for a textual renderer.

## Delivery

S3 0.20 -- S3 renderer bootstrap spike.

The milestone adds
`examples/self_hosting/assembly_renderer_bootstrap.s3`, a real S3 program that
compiles and runs through the current Python bootstrap toolchain. Its `main`
entrypoint returns `0` when the renderer-subset self-check passes.

The spike models current Python renderer-subset invariants using scalar
`tryte` and `trit` logic:

- supported Assembly directives, including `.memory`;
- supported opcodes from `TCONST` through `TBR3`;
- minimum operand shapes for representative fixed and variable arities;
- fixture line counts for `first`, `simple_call`, and `sign`;
- a negative check for an unknown opcode.

`tools/s3_program_check.py check` now includes the spike with hosted expected
return `0`. `tools/compare_assembly_renderer.py --candidate-run` continues to
execute the existing stub status and also executes the bootstrap spike, reporting
that the spike passed while the renderer implementation and full text rendering
remain `not_implemented`.

## Non-Goals

This milestone does not implement the full textual S3 Assembly renderer. It
does not make `compare --check` pass, does not alter inspect goldens or
candidate actual outputs, does not change `AssemblyProgram.render()`, and does
not change parser, lexer, semantic analysis, lowering, IR, optimizer, backend,
or emulator behavior.

`python tools/compare_assembly_renderer.py --candidate-compare-available`
continues to validate the available actual outputs with exit code 0.

`python tools/compare_assembly_renderer.py --check` continues to return exit
code 1 because the real S3 Assembly renderer is still not implemented.

## Completion

S3 0.20 is complete as a single bootstrap-spike block. There is no 0.20-B
planned.

The next phase should explicitly choose between:

- expanding S3 text/string capability enough for renderer output;
- evolving the spike toward a hosted textual representation.

No 0.21 roadmap is opened by this milestone.
