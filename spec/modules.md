# S3 modules and imports

Status: normative for Milestone 0.99.

## Goals

S3 supports deterministic compilation of multiple source files while preserving
single-file source compatibility.

This milestone does not define a package manager, dependency download, registry,
conditional import, wildcard import, filesystem access from S3 programs, or a
public linking format.

## Source units and module identity

A source unit is one S3 source string plus a deterministic logical path. Public
artifacts and diagnostics must not depend on host-specific absolute paths.

A source unit may start with an optional module declaration:

```s3
module math
```

If the declaration is absent, the module id is derived from the normalized
relative path without the `.s3` suffix. The entry unit may also be compiled as
the implicit module `main` by single-file APIs.

Module ids are dot-separated identifiers:

```text
identifier { "." identifier }
```

Two source units must not declare or derive the same module id.

## Imports

Imports appear after an optional module declaration and before the first
function declaration:

```s3
from math import abs_tryte
from util.sign import sign as classify
```

An import names one exported function from another module. The imported symbol
is visible in the importing module under its original name or explicit alias.

Rules:

- wildcard imports are not supported;
- importing the same local name twice is an error;
- importing two different exported symbols under the same local name is an
  error;
- imports are resolved by module id, not by filesystem iteration order;
- a module must not import itself directly or transitively;
- imported symbols are immutable bindings in the module-level function
  namespace.

## Visibility

Top-level functions are private by default. `export fn` declares a function that
may be imported by another module:

```s3
export fn abs_tryte(value: tryte) -> tryte:
    match value <=> 0:
        -1:
            return 0 - value
        0:
            return value
        1:
            return value
```

The entry module may call its own private functions. Other modules may call only
exported functions through explicit imports.

The entry point remains a function named `main` with no parameters. It must live
in the selected entry module. The entry `main` does not need to be exported.

## Name resolution

Each module has its own function namespace. Local functions and import aliases
share the namespace.

Resolution order for an unqualified call expression in module `M`:

1. a function declared in `M`;
2. an explicit import alias in `M`.

Ambiguous or missing names are semantic errors. Cross-module calls are lowered
to deterministic internal function names by the compiler.

Milestone 0.99 did not define qualified source calls. The later postfix
expression contract defines `module.function(...)` as member access followed by
a call suffix, resolved before lowering and never by late backend lookup. See
[postfix-expressions.md](postfix-expressions.md).

## Graph order

The compiler builds a module graph from source units, validates import edges,
rejects cycles, and emits modules in deterministic dependency order. Source
input order must not affect the final IR or Assembly when the same set of
logical source units is provided.

When several modules are otherwise unordered, ordering is lexicographic by
module id.

## Syntax mode

Modules and imports extend the current V0.6 syntax in a backward-compatible
way. The default `SyntaxMode.V0_6` remains unchanged. `SyntaxMode.V0_5` remains
legacy and does not accept module declarations or imports.

## Diagnostics

Module diagnostics use stable semantic categories. Implementations should
prefer the following codes when structured diagnostics are requested:

- `S3E_MODULE_DUPLICATE`
- `S3E_MODULE_NOT_FOUND`
- `S3E_MODULE_CYCLE`
- `S3E_MODULE_ENTRY_INVALID`
- `S3E_IMPORT_DUPLICATE`
- `S3E_IMPORT_CONFLICT`
- `S3E_IMPORT_PRIVATE_SYMBOL`
- `S3E_IMPORT_UNKNOWN_SYMBOL`

Messages may include normalized module ids and logical paths. They must not
include absolute host paths in deterministic artifacts.

## Compatibility

`compile_source(source, ...)` remains the single-file API. A source string with
no module declaration behaves as before. Existing valid programs remain valid.

Multi-file compilation uses a separate API that accepts explicit logical paths
or source units. No package manager behavior is implied.
