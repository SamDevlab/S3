# S3 records and enums

Status: normative for Milestone 1.00.

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
- field types may be scalar types, closed enum types, or other records that can
  be scalarized without cycles;
- arrays and `string` fields are not part of this milestone;
- recursive records are rejected;
- record equality is not part of this milestone;
- field mutation syntax is not part of this milestone.

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

Records are scalarized in declared field order. A record parameter lowers to its
flattened scalar fields in the internal function ABI. This is an internal
compiler convention and does not change the public S3 Assembly format.

The current IR and Assembly support only one scalar return register and expose
no pointers or aggregate return convention. Therefore, this milestone supports
record return only when the record scalarizes to exactly one scalar field.
Returning a multi-field record is rejected until a future aggregate-return ABI is
specified.

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
Record field expressions lower to their scalarized field values. Record
parameters are expanded in field order before IR generation.

No new S3 Assembly opcode is introduced by this milestone. No public format
version is bumped.

## Modules

Record and enum type names are module-local. Importing types is not part of this
milestone. Cross-module use of composite values is limited to functions already
visible through the module/import system and to scalarized ABI positions.
