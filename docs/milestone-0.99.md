# Milestone 0.99 - Modules and Imports

## Goal

Add deterministic multi-file compilation while preserving the existing
single-file `compile_source(source, ...)` API and source compatibility.

## Syntax

```s3
module app.main
from lib.math import inc
from lib.sign import sign as classify

export fn helper(value: tryte) -> tryte:
    return inc(value)

fn main() -> tryte:
    return helper(1)
```

Rules:

- `module` is optional and appears before imports and functions.
- `from module.name import symbol` imports one exported function.
- `as alias` gives the imported function a local name.
- `export fn` marks a function as visible to other modules.
- functions remain private by default.
- wildcard imports and qualified calls are not part of this milestone.

## Module Graph

The compiler uses normalized relative logical paths and module ids. Absolute
host paths are rejected by the module graph and do not enter deterministic
artifacts.

The graph validates:

- duplicate modules;
- missing modules;
- duplicate imports;
- conflicting local import names;
- direct and indirect cycles;
- missing entry modules.

Ordering is deterministic: dependencies are emitted before importers, with
lexicographic ordering for otherwise unordered modules.

## Semantic Resolution

Each module has its own function namespace. Local functions and import aliases
share that namespace. Imports may target only exported functions.

During multi-file compilation the compiler rewrites function names to internal
deterministic identifiers. The selected entry module's `main` remains `main`, so
the hosted emulator and native backend continue using the existing entry
contract.

## API

`compile_source(source, ...)` remains unchanged.

`compile_sources(sources, ..., entry_module="main")` compiles a mapping or
iterable of `(logical_path, source)` pairs. The same input set produces the same
Assembly regardless of input order.

## Non-goals

- no package manager;
- no registry;
- no dependency download;
- no wildcard import;
- no conditional import;
- no public linking format;
- no change to IR JSON or S3 Assembly format versions.

## Validation

Focused validation covers:

- single-file compatibility;
- one-module and two-module programs;
- simple, aliased, and transitive imports;
- duplicate import and import conflict diagnostics;
- missing module diagnostics;
- direct and indirect cycle diagnostics;
- private and unknown imported symbol diagnostics;
- invalid entry module diagnostics;
- deterministic output under input reordering;
- O0/O1 hosted execution;
- local collection of the native multi-module tests.
