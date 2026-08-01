# ADR-0020: Acyclic nested record layout

- Status: accepted
- Date: 2026-08-01

## Context

Milestones 1.00 and 1.02 established nominal records, enums, explicit type
exports, cross-module nominal identity, and deterministic scalarization for
record parameters. They intentionally rejected records as record fields while
the compiler had no contract for nested layout or recursive type graphs.

Milestone 1.03 allows records to contain other records when the resulting
nominal layout graph is acyclic and every reachable leaf has a known scalar
representation. The current IR, S3 Assembly, and native ABI still expose only
scalar registers and one scalar return value, so nested records must be defined
as a logical flattening contract rather than a public aggregate ABI.

## Decision

S3 records may contain local or imported record types as fields when the
nominal layout graph is acyclic. A record field may therefore be:

- `trit`;
- `tryte`;
- a closed enum without payload;
- another nominal record whose layout is acyclic and statically known.

Arrays, strings, open layouts, heap references, pointers, and payload enums
remain outside this milestone.

Nominal identity remains `ModuleId + TypeName`. Importing a record does not
copy or structurally merge its declaration. Same-name and same-shape records
from different modules remain incompatible unless their defining identity is the
same.

## Logical Layout

Nested record layout is the ordered list of scalar leaves reachable from a
record declaration.

Flattening is depth-first and follows declaration order at every record level.
The compiler must not sort fields alphabetically, by source-unit order, or by
host filesystem behavior.

Leaf rules:

- `trit` contributes one scalar leaf;
- `tryte` contributes one scalar leaf;
- a closed enum contributes one `tryte` scalar leaf;
- a nested record contributes its leaves recursively in declared order.

For example:

```s3
record Inner:
    left: trit
    right: tryte

record Outer:
    prefix: trit
    inner: Inner
    suffix: tryte
```

The logical leaf order is:

```text
Outer.prefix
Outer.inner.left
Outer.inner.right
Outer.suffix
```

This contract does not define public offsets, alignment, padding, aggregate
objects, hidden pointers, or physical layout metadata.

## Supported Value Contexts

For acyclic nested records, the implementation may support:

- record literals and nested record literals;
- module-qualified nested constructors;
- immutable local variables;
- value copies;
- record parameters;
- field and chained member access;
- branch, loop, and match contexts where the observable result is scalar;
- multi-file programs and imported record fields.

Lowering should reuse the existing scalar IR by expanding record values into
their scalar leaves. IR parameters and S3 Assembly parameters remain scalar
parameters. Native execution continues to receive scalar arguments in the
existing order and through the existing x86-64 argument/stack mechanism.

## Returns

The current return convention remains single scalar only:

- IR `RETURN` carries one value;
- S3 Assembly `TRET` carries one value;
- native x86-64 returns through `rax`.

A nested record with exactly one scalar leaf may use the existing scalar return
path when all other type rules are satisfied.

A nested record with more than one scalar leaf must be rejected before lowering.
The compiler must not return only the first leaf, discard later leaves, pack
multiple leaves into one scalar, create a hidden return pointer, use multiple
return registers, or allow emulator-only aggregate behavior.

## Cycle Detection

The semantic phase must reject recursive nominal layout graphs before lowering.
The diagnostic must be deterministic and must not rely on Python recursion
failure.

Rejected cycles include:

- direct self-reference, such as `A` containing `A`;
- two-node cycles, such as `A -> B -> A`;
- longer cycles, such as `A -> B -> C -> A`;
- cycles across modules;
- cycles through imported record types.

The diagnostic should include a stable cycle path when possible.

## Consequences

Positive consequences:

- nested value composition becomes available without public format changes;
- imported records can participate in field layout while keeping nominal
  identity;
- existing IR, verifier, optimizer, Assembly, emulator, and native backend can
  remain scalar;
- field truncation is avoided by using leaf counts before lowering.

Negative consequences:

- semantic analysis needs explicit layout graph validation;
- lowering must generalize from shallow fields to recursive leaf expansion;
- member access must preserve a nested binding path;
- aggregate returns remain unavailable until a separate ABI decision.

## Alternatives considered

**Introduce a public aggregate IR type.** Rejected for this milestone because it
would require IR, verifier, Assembly, emulator, backend, versioning, and ABI
decisions.

**Allow nested records only in the emulator.** Rejected because native execution
must remain authoritative for supported runtime behavior.

**Structural nested layout compatibility.** Rejected because it would violate
the nominal identity established by ADR-0019.

**Return multi-leaf records by truncating to the first leaf.** Rejected because
it silently loses data and conflicts with the single-scalar return contract.

## Compatibility

Existing programs remain valid. This ADR does not add public IR instructions,
S3 Assembly directives, native ABI forms, diagnostic schema fields, package
manager behavior, tags, releases, or public version bumps.
