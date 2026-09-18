# Self-hosted implementation

This directory contains experimental S3-written compiler, assembler, runtime,
and standard-library components. No Python bootstrap component should be treated
as part of this S3 core.

Python remains the reference compiler and default path. The project currently
classifies **full compiler self-hosting as a deferred research frontier**, not as
an active release or roadmap gate. See [`docs/selfhost/STATUS.md`](../docs/selfhost/STATUS.md),
[`docs/selfhost/LESSONS.md`](../docs/selfhost/LESSONS.md), and
[`docs/selfhost/REENTRY_CRITERIA.md`](../docs/selfhost/REENTRY_CRITERIA.md).

Functions, ternary control flow, local memory, static arrays, modules, records,
enums, static text, fixed-layout payload enums, bounded text, Assembly parsing,
and other incremental contracts remain useful differential evidence. Existing
milestone/component results keep their historical status; none of those bounded
results should be interpreted as proof of a complete self-hosted compiler.

Components in this directory are small, explicit comparison targets unless a
specific milestone says otherwise. They do not replace the Python compiler, do
not become default compiler paths, and must not silently depend on host-side
semantic compilation when used for self-host research.

The first and second stage components keep scalar public returns. Third-stage
components under `selfhost/results/` intentionally exercise aggregate returns
and explicit structured result APIs while preserving Python as the reference.

Bounded text components under `selfhost/text/` use fixed arrays, aggregate
results, explicit matches, ASCII code units, and scalar cursor/span indices.
They do not provide a complete compiler frontend, filesystem, heap, pointer,
dynamic text, or Unicode model.

Assembly components under `selfhost/assembly/` include an opcode classifier,
bounded tokenizer, bounded parser kernel, and frontend candidate. These remain
bounded comparison targets. They consume bounded ASCII text and explicit
cursors, return fixed-layout events, summaries, or structured errors, and do
not replace the Python Assembly parser, verifier, renderer, CLI, emulator,
native backend, or golden contracts.

The `selfhost/substrate/` components are the first bounded compiler-substrate
shape: text-keyed maps, direct-ID arenas, source cursors, lexical-state
records, output-sink state, and a compiler-context shape. They are ordinary S3
representability artifacts backed by the normative hosted contracts in
[`docs/spec/compiler-substrate-v1.md`](../docs/spec/compiler-substrate-v1.md).
They intentionally stop before lexer/parser/semantic compiler implementation;
full self-hosting remains deferred.

## Full self-host policy

A future full self-host attempt must be design-first. Before implementation is
authorized it must demonstrate one generic compiler architecture:

```text
source
  -> lexer
  -> parser
  -> generic AST/HIR
  -> semantic passes
  -> generic IR
  -> verifier
  -> emitter
  -> compile_program
```

Vertical slices may test this architecture, but production behavior must not be
organized around slice or fixture identity. A new implementation generation is
not authorized by the existence of additional language/runtime features alone.
