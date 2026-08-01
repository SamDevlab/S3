# ADR-0019: Cross-module nominal type identity

- Status: accepted
- Date: 2026-08-01

## Context

Milestone 0.99 introduced deterministic modules and function imports.
Milestone 1.00 introduced module-local records and enums. Milestone 1.02-B
added uniform postfix syntax, qualified calls, and qualified enum variants, but
nominal type declarations still remain owned by their defining module.

The next step is to allow modules to export nominal record and enum types while
preserving deterministic identity and layout. S3 must avoid structural typing,
late backend name parsing, filesystem-order behavior, and hidden reexports.

## Decision

A nominal type identity is:

```text
ModuleId + TypeName
```

Two nominal types with the same source name are distinct when they are declared
by different modules. They are compatible only when both the defining module id
and the type name match after deterministic module resolution.

Records and enums become exportable with the same explicit visibility model as
functions:

```s3
export record Point:
    x: tryte
    y: tryte

export enum Sign:
    Negative
    Zero
    Positive
```

Private record and enum declarations remain module-local. A type from another
module is visible only through an explicit import of that exported type:

```s3
from geometry import Point
from signs import Sign
```

Type import aliases are not part of this milestone. Existing function import
aliases remain unchanged. Wildcard imports, conditional imports, and general
reexports remain unsupported.

## Namespaces

Modules keep separate symbol categories for:

- module roots;
- functions;
- nominal types;
- enum variants;
- record fields;
- runtime values.

Function imports and type imports may share source syntax, but the compiler
must resolve them into distinct function and type namespaces. A local
declaration or import that would make a type reference ambiguous is rejected
before semantic analysis relies on it.

Runtime bindings still shadow module and type roots in expression position.
Record fields and enum variants are never imported as standalone symbols.

## Qualified Type Syntax

The source language recognizes exported types through module-qualified member
syntax when the module is visible:

```s3
geometry.Point(x: 1, y: 2)
signs.Sign.Positive
```

Unqualified type positions use local type declarations or explicit type
imports:

```s3
from geometry import Point

fn translate(point: Point) -> Point:
    return Point(x=point.x + 1, y=point.y)
```

The parser remains syntax-only. It does not decide whether `A.B` is a module
type, enum variant, record field, or invalid member. Semantic analysis owns the
category decision, and lowering consumes resolved identities.

## Layout

The defining module owns layout. Importing a type does not recreate the record
or enum in the consumer module.

Record field order, field types, enum variant order, and enum discriminants are
computed from the defining declaration. Source unit input order, dictionary
order, host paths, and filesystem iteration order must not affect layout.

Same-name records in different modules may have identical fields, but they
remain incompatible unless their nominal identities match. Same-name enums in
different modules likewise remain incompatible.

## Diagnostics

The compiler must distinguish:

- missing exported type;
- private type imported from another module;
- import conflicts between type names;
- nominal mismatch between same-shaped types from different modules;
- invalid qualified type member;
- imported record used as a field while nested records remain unsupported.

Diagnostics should use existing semantic/module categories and codes where
possible. This ADR does not require a public diagnostic schema change.

## Reexports

General reexport is not part of Milestone 1.02-C. A module may use imported
types in its own exported function signatures where the implementation supports
that, but importing a type through a third module as if it were reexported is
not supported until a separate contract exists.

## Consequences

Positive consequences:

- nominal identity becomes deterministic across modules;
- same-name types from different modules remain safely distinct;
- record and enum layout ownership stays with the defining module;
- type imports do not require a package manager, registry, or public linking
  format;
- lowering can keep using existing scalarized layouts.

Negative consequences:

- module symbol tables must carry exported type symbols in addition to
  functions;
- qualified construction needs semantic resolution before record lowering;
- type import aliases and reexports remain intentionally unavailable;
- diagnostics must report type visibility separately from function visibility.

## Alternatives considered

**Structural typing across modules.** Rejected because it would make same-shaped
records interchangeable, weakening nominal identity and making layout
compatibility depend on shape rather than declaration ownership.

**Treat imported records as copied local declarations.** Rejected because it
would duplicate layout authority in consumer modules and make diagnostics
harder to tie back to the defining module.

**Allow wildcard type imports.** Rejected because it obscures which module owns
a type and increases collision risk without a package-manager contract.

**Add type import aliases immediately.** Rejected for this milestone because
the existing function alias contract does not yet define mixed function/type
alias collisions or reexport behavior.

## Compatibility

Existing single-file programs and existing module function imports remain
valid. This ADR does not add public IR instructions, S3 Assembly directives, ABI
forms, native interfaces, diagnostic schema fields, tags, releases, or package
manager behavior.
