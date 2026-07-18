# S3 0.19 Roadmap

Status: closed

## Objective

Adopt the `AssemblyTextRenderer` / `render_supported_program(program)` path
inside the real Python `AssemblyProgram.render()` implementation while
preserving byte-for-byte Assembly output. This is still Python-side renderer
infrastructure; it is not the real S3 Assembly renderer.

## Delivery

S3 0.19 -- AssemblyProgram render parity adoption.

The supported `AssemblyProgram` adapter now covers the Assembly text currently
emitted by `AssemblyProgram.render()`:

- `.s3asm`, `.function`, `.param`, `.register`, `.memory`, `.label`, and `.end`;
- `TCONST`, `TMOV`, `TINV`, `TADD`, `TMIN`, `TMAX`, `TCMP`, `TCALL`, `TLOAD`,
  `TSTORE`, `TRET`, `TJMP`, and `TBR3`;
- optional source metadata, rendered only when present;
- function, parameter, register, memory, block, and instruction order exactly
  as stored in the model.

`AssemblyProgram.render()` now delegates to `render_supported_program(self)` and
returns the resulting `StaticTextDocument.text`, preserving the public
signature and return type.

The previous `render_first_program`, `render_simple_call_program`, and
`render_sign_program` wrappers remain available. They continue to validate their
fixture-specific shapes and still delegate byte emission to the common supported
path.

## Non-Goals

This milestone does not implement the S3 renderer, does not alter actual
outputs, does not alter inspect goldens, does not alter the backend or compiler
pipeline semantics, and does not change the global renderer comparison result.

`python tools/compare_assembly_renderer.py --candidate-compare-available`
continues to validate the available actual outputs with exit code 0.

`python tools/compare_assembly_renderer.py --check` continues to return exit
code 1 because the real S3 Assembly renderer is still not implemented.

## Completion

S3 0.19 is complete as a single adoption block. There is no 0.19-B planned.

The next phase should explicitly choose between:

- expanding language/runtime features needed to make a renderer in S3 viable;
- starting a separate experimental S3 renderer path.

No 0.20 roadmap is opened by this milestone.
