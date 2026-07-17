# S3 0.16 Roadmap

Status: closed

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

## 0.16-C: Renderer Core Sign Path

Status: completed

0.16-C routes `build_sign_fixture_assembly_text()` through the same minimal
renderer core. The current API was sufficient for the sign fixture, including
`TBR3`, multiple labels, source metadata, the blank line between functions, and
the final `.end` directive.

`first`, `simple_call`, and `sign` now use `AssemblyTextRenderer`. All three
candidate actual outputs remain byte-for-byte stable against their
LF-normalized inspect goldens, and neither actual outputs nor inspect goldens
change.

This closes S3 0.16. The milestone still does not use the real
`AssemblyProgram` renderer and does not implement the S3 renderer.

## Current State

- `first`: available, passed, and routed through the renderer core;
- `simple_call`: available, passed, and routed through the renderer core;
- `sign`: available, passed, and routed through the renderer core;
- `--candidate-compare-available`: expected exit code 0;
- `--check`: expected exit code 1, blocked because the real S3 renderer is
  still not implemented.

## Closure

There is no planned 0.16-D. Any future change should happen in a separate
milestone that either evaluates controlled coupling to the real
`AssemblyProgram` model or starts the real S3 renderer path with byte-for-byte
comparison coverage. Any future change to the global `--check` result must
happen separately, with a real S3 renderer implementation.
