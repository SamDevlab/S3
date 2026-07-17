# S3 0.17 Roadmap

Status: closed

## Objective

Approach the real `AssemblyProgram` model through small, tested adapters that
render with `AssemblyTextRenderer`, without changing the global renderer
candidate state before a real S3 renderer exists.

S3 0.17 keeps the 0.16 safety boundary intact:
`python tools/compare_assembly_renderer.py --candidate-compare-available`
validates the available actual outputs, and
`python tools/compare_assembly_renderer.py --check` remains blocked with exit
code 1 until a real S3 renderer implementation can produce comparable output.

## 0.17-A: AssemblyProgram Adapter First Path

Status: completed

0.17-A adds a minimal `AssemblyProgram` to `AssemblyTextRenderer` adapter for
the `first` fixture path. The adapter reads the real `AssemblyProgram` model,
validates the narrow `first` subset, emits through `AssemblyTextRenderer`, and
returns a `StaticTextDocument`.

The `first` adapter path remains byte-for-byte stable against the
LF-normalized inspect golden and the versioned candidate actual output. The
actual outputs and inspect goldens are not changed.

This does not replace `AssemblyProgram.render()` globally, does not implement
the S3 renderer, does not migrate `simple_call` or `sign` to the adapter, and
does not make the global renderer candidate check pass.

## 0.17-B: AssemblyProgram Adapter Simple Call Path

Status: completed

0.17-B extends the controlled `AssemblyProgram` to `AssemblyTextRenderer`
adapter to the `simple_call` fixture path. The adapter reads the real
two-function `AssemblyProgram` model, validates the narrow `add`/`main` shape
including parameters, registers, `TCALL`, and source metadata, emits through
`AssemblyTextRenderer`, and returns a `StaticTextDocument`.

The `simple_call` adapter path remains byte-for-byte stable against the
LF-normalized inspect golden and the versioned candidate actual output. The
actual outputs and inspect goldens are not changed.

This does not replace `AssemblyProgram.render()` globally, does not implement
the S3 renderer, does not migrate `sign` to the adapter, and does not make the
global renderer candidate check pass.

## 0.17-C: AssemblyProgram Adapter Sign Path

Status: completed

0.17-C extends the controlled `AssemblyProgram` to `AssemblyTextRenderer`
adapter to the `sign` fixture path. The adapter reads the real two-function
`AssemblyProgram` model, validates the narrow `sign`/`main` shape including
parameters, registers, multiple labels, `TCMP`, `TBR3`, `TCALL`, and source
metadata, emits through `AssemblyTextRenderer`, and returns a
`StaticTextDocument`.

The `sign` adapter path remains byte-for-byte stable against the LF-normalized
inspect golden and the versioned candidate actual output. The actual outputs
and inspect goldens are not changed.

This does not replace `AssemblyProgram.render()` globally, does not implement
the S3 renderer, and does not make the global renderer candidate check pass.

## Current State

- `first`: available, passed, routed through the renderer core, and proven
  through the controlled `AssemblyProgram` adapter;
- `simple_call`: available, passed, routed through the renderer core, and
  proven through the controlled `AssemblyProgram` adapter;
- `sign`: available, passed, routed through the renderer core, and proven
  through the controlled `AssemblyProgram` adapter;
- `--candidate-compare-available`: expected exit code 0;
- `--check`: expected exit code 1, blocked because the real S3 renderer is
  still not implemented.

## Completion

S3 0.17 is complete after three deliveries:

- 0.17-A: AssemblyProgram adapter first path;
- 0.17-B: AssemblyProgram adapter simple_call path;
- 0.17-C: AssemblyProgram adapter sign path.

There is no 0.17-D planned. The next phase should evaluate a real renderer or
controlled generalization separately. Any future change to the global `--check`
result must happen separately, with a real S3 renderer implementation.
