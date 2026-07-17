# S3 0.16 Roadmap

Status: open

## Objective

Begin the practical path from fixture-by-fixture probes toward an incremental
Assembly renderer core, without claiming that the real S3 renderer exists.

S3 0.16 keeps the 0.15 safety decision intact:
`python tools/compare_assembly_renderer.py --candidate-compare-available`
validates the currently available actual outputs, and
`python tools/compare_assembly_renderer.py --check` remains blocked with exit
code 1 until a real S3 renderer implementation can produce comparable output.

## 0.16-A: Renderer Core First Path

Status: completed

0.16-A adds a minimal Python Assembly text renderer core and routes the
`first` fixture through it. The core uses `StaticTextLineEmitter` underneath and
provides structured operations for:

- Assembly header emission;
- function headers;
- parameter and register declarations;
- labels;
- aligned instructions with source metadata;
- function endings;
- final `StaticTextDocument` construction.

The `first` path remains byte-for-byte stable against the LF-normalized inspect
golden and the versioned candidate actual output. The actual outputs for
`first`, `simple_call`, and `sign` are not changed, and the inspect goldens are
not changed.

This is an incremental Python-side bridge. It does not render arbitrary
`AssemblyProgram` values, does not implement the S3 renderer, and does not make
the global renderer candidate check pass.

## 0.16-B: Renderer Core Simple Call Path

Status: completed

0.16-B routes `build_simple_call_fixture_assembly_text()` through the same
minimal renderer core. The current API was sufficient, including parameters,
multiple functions, blank lines between functions, and `TCALL` as a structured
instruction with a callee operand.

`first` and `simple_call` now use `AssemblyTextRenderer`. `sign` intentionally
remains on the previous fixture-probe path for this delivery. All three
candidate actual outputs remain byte-for-byte stable against their
LF-normalized inspect goldens, and neither actual outputs nor inspect goldens
change.

This still does not use the real `AssemblyProgram` renderer and does not
implement the S3 renderer.

## Current State

- `first`: available and passed;
- `simple_call`: available and passed;
- `sign`: available and passed;
- `--candidate-compare-available`: expected exit code 0;
- `--check`: expected exit code 1, blocked because the real S3 renderer is
  still not implemented.

## Next Focus

Apply the renderer core to `sign` only if that can preserve byte-for-byte output
without broadening the abstraction too far. Any future change to the global
`--check` result must happen separately, with a real S3 renderer path and
byte-for-byte comparison coverage.
