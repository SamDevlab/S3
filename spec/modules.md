# S3 modules and imports

Status: normative for Milestone 0.99 modules, Milestone 1.02-C exported
nominal types, and Milestone 1.03 imported records used as acyclic nested
fields, with Milestone 1.04 static text leaves in imported records and
Milestone 1.05 payload enum layouts.

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

An import names one exported function from another module. Beginning with
Milestone 1.02-C, the same import form may also name one exported nominal type
from another module. The imported symbol is visible in the corresponding
function or type namespace of the importing module.

Rules:

- wildcard imports are not supported;
- importing the same local name twice is an error;
- importing two different exported symbols under the same local name is an
  error;
- imports are resolved by module id, not by filesystem iteration order;
- a module must not import itself directly or transitively;
- imported function symbols are immutable bindings in the module-level function
  namespace;
- imported type symbols are immutable bindings in the module-level type
  namespace;
- type import aliases are not part of Milestone 1.02-C.

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

Records and enums follow the same explicit visibility model in Milestone
1.02-C. A private record or enum is visible only within its defining module.
`export record` and `export enum` declare nominal types that may be imported by
other modules:

```s3
export record Point:
    x: tryte
    y: tryte

export enum Sign:
    Negative
    Zero
    Positive
```

The entry point remains a function named `main` with no parameters. It must live
in the selected entry module. The entry `main` does not need to be exported.

## Name resolution

Each module has its own function namespace. Local functions and import aliases
share the namespace.

Each module also has its own type namespace. Local records, local enums, and
explicit imported types share that namespace. Nominal identity is not the local
spelling alone; it is the defining `ModuleId + TypeName`.

Resolution order for an unqualified call expression in module `M`:

1. a function declared in `M`;
2. an explicit import alias in `M`.

Ambiguous or missing names are semantic errors. Cross-module calls are lowered
to deterministic internal function names by the compiler.

Milestone 0.99 did not define qualified source calls. Milestone 1.02-B defines
and implements `module.function(...)` as member access followed by a call
suffix, resolved before lowering and never by late backend lookup. See
[postfix-expressions.md](postfix-expressions.md).

Milestone 1.02-C extends module resolution to exported nominal types. A
module-qualified type such as `geometry.Point` denotes the type declared as
`Point` by module `geometry`, not a copied type in the consumer module. Same-name
types from different modules remain incompatible unless their defining module id
also matches.

Imported nominal values keep that defining identity when they flow through
variables, parameters, supported single-field returns, construction, field
access, enum variants, and match. Multi-field record returns remain outside the
current scalar-return ABI and are rejected before lowering.

Beginning with Milestone 1.03, an imported record type may be used as a field of
another record when the full nominal layout graph is acyclic. The leaf order is
the defining modules' declared field order, recursively expanded depth-first by
the canonical record layout model. Source-unit input order and import order must
not affect the resulting IR or Assembly. Same-name or same-shape records from
different modules remain incompatible because nominal identity is still the
defining `ModuleId + TypeName`.

Beginning with Milestone 1.04, `string` may appear as a scalar static-text leaf
inside local or imported records. Its module behavior is the same as other
scalar leaves: the defining record owns the declared field order, and consumers
receive the scalarized handle through explicit imports and calls. This does not
add dynamic text, heap allocation, or an aggregate-return convention.

Beginning with Milestone 1.05, imported payload enum values preserve the
defining enum's fixed tag-plus-payload layout. Qualified construction and
qualified match labels use the defining module's discriminants, payload field
order, cell width, and inactive slot policy. Payload field types must be visible
where they are named in source, and nominal identity remains `ModuleId +
TypeName`; same-name or same-shape payload enums from different modules remain
incompatible.

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

Milestone 1.02-C type diagnostics should reuse the same module/import phase and
codes where possible for missing or private exported types, and semantic
diagnostics for nominal type mismatches.

## Compatibility

`compile_source(source, ...)` remains the single-file API. A source string with
no module declaration behaves as before. Existing valid programs remain valid.

Multi-file compilation uses a separate API that accepts explicit logical paths
or source units. No package manager behavior is implied.
