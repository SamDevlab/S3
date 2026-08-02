# S3 records and enums

Status: normative for Milestone 1.00 records/enums, Milestone 1.02-C
cross-module nominal values, Milestone 1.03 acyclic nested records, Milestone
1.04 fixed-capacity static text leaves, Milestone 1.05 fixed-layout enum
payloads, Milestone 1.07 unified fixed value layouts, and Milestone 1.12 fixed
array fields.

## Scope

S3 adds nominal records and closed enums as compile-time known types.

This milestone does not add classes, methods, inheritance, traits, interfaces,
generics, reflection, heap allocation, pointers, open enums, dynamic type
extension, aggregate returns, exceptions, or implicit error propagation.

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
- field types may be `trit`, `tryte`, `string`, fixed `trit`/`tryte` arrays,
  closed enum types, or acyclic record types;
- record equality is not part of this milestone;
- field mutation syntax is not part of this milestone.

## Nested Record Layout

Beginning with Milestone 1.03, a record may directly or indirectly contain
another record when the nominal layout graph is acyclic and every reachable leaf
has a known scalar representation.

Nested layout is logical scalar leaf order, not public offsets or alignment.
Flattening is depth-first and follows declaration order at every record level.
The compiler must not sort nested fields alphabetically or by source-unit order.
The canonical implementation contract is the semantic fixed value layout for
the record type. `SemanticModel.record_leaves()` is a compatibility query
derived from that layout for leaf paths, leaf types, flattening order,
parameter scalarization, copies, member access, and return classification.
`record_leaf_count()` is a derived query over that same layout. Lowering, tests,
and native coverage must not maintain a parallel layout algorithm.

Leaf rules:

- `trit` contributes one scalar leaf;
- `tryte` contributes one scalar leaf;
- `string` contributes one scalar handle leaf;
- a fixed array contributes one leaf per element in increasing index order;
- a closed enum contributes one `tryte` scalar leaf;
- a nested record contributes its leaves recursively in declared order.

Recursive record graphs remain invalid. This includes direct self-reference,
indirect cycles, and cycles through imported record types. Arrays of records,
enums, strings, and arrays remain outside the current composition contract.

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

Enums are closed nominal sets of variants. Variants may have no payload or a
fixed set of named payload fields:

```s3
enum Sign:
    Negative
    Zero
    Positive

enum Result:
    Ok(value: tryte)
    Error(code: tryte, label: string)
```

Rules:

- enum names share the module type namespace;
- variant names must be unique within the enum;
- variants are ordered by declaration order;
- discriminants are deterministic `tryte` values starting at `0`;
- payload field names must be unique within each variant;
- payload field order is declaration order and is part of layout;
- payload field types may be `trit`, `tryte`, `string`, closed enum types, or
  acyclic record types;
- enums from different types are incompatible even if they have equal variants.

Payload enum layout is fixed by enum type:

- cell 0 is the `tryte` tag discriminant;
- payload cells begin at cell 1;
- the enum width is `1 + max(payload_leaf_count)` across variants;
- each payload cell position has one canonical scalar slot type;
- variants whose payload leaves conflict with the canonical slot type at the
  same position are semantic errors;
- no-payload variants in a payload enum still occupy the full enum width;
- inactive payload slots are initialized deterministically according to their
  canonical scalar slot type;
- payload record leaves use `SemanticModel.record_leaves()` order;
- payload enum leaves are allowed only when acyclic and statically sized.

The current implementation must not encode payloads by truncating to the tag,
truncating to the first payload leaf, packing without proof of capacity, or
inventing a hidden aggregate return path.

Construction uses qualified variant syntax. Payload variants require named
payload arguments:

```s3
value: Sign = Sign.Negative
result: Result = Result.Ok(value=3)
error: Result = Result.Error(code=-1, label="parse")
```

No-payload enum equality compares discriminants as before. Equality for
payload-carrying enum types is not part of the initial payload milestone unless
all payload cells are explicitly included by a later contract.

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

Payload bindings are allowed only on explicit enum variant arms:

```s3
match result:
    Result.Ok(value):
        return value
    Result.Error(code, label):
        return code
```

Bindings are scoped to the selected arm and typed from the variant payload
field declaration. Fallback arms cannot bind payload fields. Inactive slots are
not directly observable through the source language.

Duplicate enum arms are semantic errors. A fallback followed by explicit arms is
already invalid under the existing match shape. Arms for variants of a different
enum type are semantic errors.

## Lowering

No-payload enums lower to existing `tryte` registers holding the documented
discriminant. Payload-carrying enums lower to existing scalar registers in the
fixed tag-plus-payload cell order. Record field expressions lower to their
supported field values. Record and payload enum parameters are expanded in
canonical cell order before IR generation. Lowering consumes the semantic fixed
value layout and the compatibility `SemanticModel.enum_layout()` query derived
from it rather than recalculating enum payload layout.

No new S3 Assembly opcode is introduced by this milestone. No public format
version is bumped.

## Unified Fixed Value Layout

Beginning with Milestone 1.07, records, enums, scalar values, and fixed static
text handles share one semantic fixed value layout contract. The layout is
logical and target-independent: it records ordered scalar cells, stable source
paths, scalar cell types, nominal dependencies, and return classification. It
does not define physical offsets, native register assignment, stack storage,
alignment, padding, or public Assembly encoding.

Existing record and enum layout APIs remain compatibility wrappers over the
canonical layout. New compiler code that needs a type-wide layout or return
answer should query the canonical fixed value layout instead of reimplementing
record-specific or enum-specific traversal.

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
