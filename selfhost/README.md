# Self-hosted implementation

This directory is reserved for future S3 compiler, assembler, runtime, and
standard-library components written in S3. No Python bootstrap component should
be treated as part of this S3 core.

Functions, ternary control flow, local memory, static arrays, modules, records,
enums, static text, and fixed-layout payload enums now have incremental
contracts. Complete self-hosting is still future work: Python remains the
reference compiler and default path.

Components in this directory are small, pure differential references. They do
not replace the Python compiler, do not access the filesystem, do not depend on
heap allocation, and do not become default compiler paths.

The first and second stage components keep scalar public returns. Third-stage
components under `selfhost/results/` intentionally exercise aggregate returns
and explicit structured result APIs while preserving Python as the reference.

Bounded text components under `selfhost/text/` are experimental differential
references for a later tokenizer/parser. They use fixed arrays, aggregate
results, explicit matches, ASCII code units, and scalar cursor/span indices.
They do not replace Python or provide filesystem, heap, pointer, dynamic text,
or Unicode behavior.
