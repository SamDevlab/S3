# S3 records and enums

Status: normative for Milestone 1.00 records/enums, Milestone 1.02-C
cross-module nominal values, Milestone 1.03 acyclic nested records, and
Milestone 1.04 fixed-capacity static text leaves.

## Scope

S3 adds nominal records and closed enums as compile-time known types.

This milestone does not add classes, methods, inheritance, traits, interfaces,
generics, reflection, heap allocation, pointers, open enums, enum payloads, or
dynamic type extension.

## Records

Records declare a fixed ordered set of named fields:

```s3
record Pair:
    left: tryte
    right: trit
```

Rules:

- record names share the module type namespace;
- field order is declaration order and is part of layout;
- field names must be unique;
- field types may be `trit`, `tryte`, `string`, closed enum types, or acyclic
  record types;
- array fields are not part of this milestone;
- record equality is not part of this milestone;
- field mutation syntax is not part of this milestone.

## Nested Record Layout

Beginning with Milestone 1.03, a record may directly or indirectly contain
another record when the nominal layout graph is acyclic and every reachable leaf
has a known scalar representation.

Nested layout is logical scalar leaf order, not public offsets or alignment.
Flattening is depth-first and follows declaration order at every record level.
The compiler must not sort nested fields alphabetically or by source-unit order.
`SemanticModel.record_leaves()` is the canonical implementation contract for
leaf paths, leaf types, flattening order, parameter scalarization, copies,
member access, and return classification. `record_leaf_count()` is a derived
query over that same layout. Lowering, tests, and native coverage must not
maintain a parallel layout algorithm.

Leaf rules:

- `trit` contributes one scalar leaf;
- `tryte` contributes one scalar leaf;
- `string` contributes one scalar handle leaf;
- a closed enum contributes one `tryte` scalar leaf;
- a nested record contributes its leaves recursively in declared order.

Recursive record graphs remain invalid. This includes direct self-reference,
indirect cycles, and cycles through imported record types. Arrays of records and
arrays inside records remain outside the current composition contract.

Construction uses named fields:

```s3
p: Pair = Pair(left=3, right=-1)
```

Every field must be provided exactly once. Extra or missing fields are semantic
errors. Field access uses postfix dot syntax:

```s3
return p.left
```

## Record ABI

Records are scalarized in declared depth-first leaf order across the supported
field types. A record parameter lowers to its flattened scalar leaves in the
internal function ABI. This is an internal compiler convention and does not
change the public S3 Assembly format.

The current IR and Assembly support only one scalar return register and expose
no pointers or aggregate return convention. Therefore, this milestone supports
record return only when the record contains exactly one scalar leaf. Returning a
record with multiple scalar leaves is rejected until a future aggregate-return
ABI is specified.

## Enums

Enums are closed nominal sets of variants without payload:

```s3
enum Sign:
    Negative
    Zero
    Positive
```

Rules:

- enum names share the module type namespace;
- variant names must be unique within the enum;
- variants are ordered by declaration order;
- discriminants are deterministic `tryte` values starting at `0`;
- enum payloads are not part of this milestone;
- enums from different types are incompatible even if they have equal variants.

Payload-carrying enum variants and structured result enums are blocked on the
ADR-0021 tag-plus-payload architecture decision. The current implementation
must not encode payloads by truncating to the tag, truncating to the first
payload leaf, or inventing a hidden aggregate return path.

Construction uses qualified variant syntax:

```s3
value: Sign = Sign.Negative
```

Enums compare with `==` and `!=` only when both operands have the same enum
type. The result is `trit`.

## Enum Match

`match` over an enum selector must be exhaustive unless an `else` fallback is
present:

```s3
match value:
    Sign.Negative:
        return -1
    Sign.Zero:
        return 0
    Sign.Positive:
        return 1
```

Duplicate enum arms are semantic errors. A fallback followed by explicit arms is
already invalid under the existing match shape. Arms for variants of a different
enum type are semantic errors.

## Lowering

Enums lower to existing `tryte` registers holding the documented discriminant.
Record field expressions lower to their supported field values. Record
parameters are expanded in field order before IR generation.

No new S3 Assembly opcode is introduced by this milestone. No public format
version is bumped.

## Modules

Record and enum type names are module-local in their declaration. Milestone
1.02-C allows explicitly exported record and enum types to be imported by other
modules without changing their nominal identity. The identity of a nominal type
is its defining `ModuleId + TypeName`.

Cross-module use of composite values is limited to functions and types visible
through the module/import system and to supported scalarized ABI positions.
Record fields may use local or imported record types when the full nested
layout graph is acyclic.

Milestone 1.02-B adds qualified source syntax for module functions and enum
variants. It does not change the module-local ownership of record and enum
types. A visible qualified function may return a supported single-field record,
and the caller may immediately read that field through the existing scalarized
return convention.

Milestone 1.02-C extends that ownership model across module boundaries:

- `export record` and `export enum` make a nominal type importable;
- private records and enums remain unavailable to other modules;
- same-name types declared in different modules are incompatible;
- imported enum values may be matched using the defining enum's variants;
- imported record values may be declared, passed, returned, constructed, and
  projected through their fields when their field types are otherwise supported;
- imported records may be used as fields beginning with Milestone 1.03 when
  their layout graph is acyclic;
- imported multi-leaf record values may be passed and projected in supported
  scalarized positions, but returning them remains rejected until an
  aggregate-return ABI is specified.
