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
heap allocation, and do not use aggregate returns.
