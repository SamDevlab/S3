# S3 0.18 Roadmap

Status: closed

## Objective

Consolidate the controlled `AssemblyProgram` adapter work from S3 0.17 into a
single supported renderer subset path, while keeping the same safety boundary:
this is still a Python-side bridge through `AssemblyTextRenderer`, not the real
S3 renderer.

S3 0.18 keeps the comparison contract unchanged:
`python tools/compare_assembly_renderer.py --candidate-compare-available`
validates the available actual outputs, and
`python tools/compare_assembly_renderer.py --check` remains blocked with exit
code 1 until a real S3 renderer implementation can produce comparable output.

## Supported AssemblyProgram Renderer Subset

Status: completed

0.18 adds `AssemblyProgramTextAdapter.render_supported_program(program)` and the
module-level `render_supported_program(program)` wrapper. This path validates a
common supported subset and emits through `AssemblyTextRenderer`, returning a
`StaticTextDocument`.

The subset is intentionally limited to the behavior already proven by the
`first`, `simple_call`, and `sign` fixture paths:

- Assembly format version `0.5.0`;
- one or more functions, emitted in model order;
- unique function names;
- no function memory objects;
- one or more blocks per function, emitted in model order;
- unique block labels per function;
- one or more instructions per block;
- source metadata on rendered instructions;
- opcodes `TCONST`, `TMOV`, `TINV`, `TADD`, `TCMP`, `TCALL`, `TRET`, and
  `TBR3`;
- `TCALL` with one or two argument registers, matching the currently proven
  fixture arities.

The previous `render_first_program`, `render_simple_call_program`, and
`render_sign_program` entry points remain available. They keep their
fixture-specific validation and delegate the actual byte emission to
`render_supported_program`.

The `first`, `simple_call`, and `sign` outputs remain byte-for-byte stable
against their LF-normalized inspect goldens and versioned candidate actual
outputs. Neither actual outputs nor inspect goldens change.

This does not replace `AssemblyProgram.render()` globally, does not implement
the S3 renderer, does not inspect or rewrite goldens, and does not make the
global renderer candidate check pass.

## Current State

- `first`: available, passed, routed through the renderer core, proven through
  the controlled `AssemblyProgram` adapter, and now emitted by the common
  supported subset path;
- `simple_call`: available, passed, routed through the renderer core, proven
  through the controlled `AssemblyProgram` adapter, and now emitted by the
  common supported subset path;
- `sign`: available, passed, routed through the renderer core, proven through
  the controlled `AssemblyProgram` adapter, and now emitted by the common
  supported subset path;
- `--candidate-compare-available`: expected exit code 0;
- `--check`: expected exit code 1, blocked because the real S3 renderer is
  still not implemented.

## Completion

S3 0.18 opened and closed with this supported subset consolidation. There is no
0.18-B planned. Any future expansion of the supported subset, any replacement
of `AssemblyProgram.render()`, or any change to the global `--check` result
must happen separately and only with explicit comparison coverage.
