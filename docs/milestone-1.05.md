# Milestone 1.05 - Fixed-Layout Enum Payloads and Structured Errors

Status: In progress - architecture accepted

Milestone 1.05 was audited after the completion of acyclic nested records and
fixed-capacity static text values. The audit found that payload enums required
a public syntax and layout decision before implementation. ADR-0021 is now
accepted and selects a fixed tagged multi-cell layout.

## Architecture Audit

Current enum support is intentionally scalar:

- AST `EnumVariant` stores only a name;
- grammar accepts only one bare identifier per enum variant;
- semantic analysis maps each variant to a deterministic `tryte`
  discriminant;
- construction syntax is `Enum.Variant`;
- equality and inequality compare only same-type discriminants;
- enum `match` validates exhaustiveness and duplicate arms;
- match labels have no binding form;
- imported enum values preserve defining nominal identity;
- lowering emits the existing scalar `tryte` discriminant;
- IR, S3 Assembly, emulator, and native x86-64 see one scalar value.

Payload enums require a new value model: tag plus payload. The requested
payloads include scalar leaves, acyclic records, nested records, and fixed text
handles. Multi-leaf payloads cannot be returned under the current scalar return
convention, and truncating to the tag or first payload leaf would be incorrect.

## Architecture Decision

[ADR-0021](decisions/ADR-0021-enum-payload-layout-gate.md) records the accepted
architecture decision. The selected representation is:

- fixed width per enum type;
- tag in cell 0 as a `tryte` discriminant;
- payload cells after the tag;
- payload leaves in declaration order;
- record payloads scalarized by `SemanticModel.record_leaves()`;
- inactive slots initialized deterministically;
- no public IR, Assembly, or scalar ABI change.

The branch keeps `tests/test_enum_payload_architecture_gate.py` as an xfail
until parser, semantic analysis, lowering, and match bindings implement the
accepted contract.

## Specification

Payload variants use named payload fields:

```s3
enum Result:
    Ok(value: tryte)
    Error(code: tryte, label: string)
```

Construction uses qualified variants with named payload arguments:

```s3
value: Result = Result.Ok(value=3)
error: Result = Result.Error(code=-1, label="parse")
```

Match bindings use the variant label plus binding names:

```s3
match value:
    Result.Ok(value):
        return value
    Result.Error(code, label):
        return code
```

Bindings are arm-local and typed from the variant declaration.

## Preserved Invariants

- no aggregate returns;
- no hidden return pointer;
- no multi-register return;
- no stack return area;
- no implicit packing;
- no tag-only or first-leaf truncation;
- no heap allocation;
- no public IR or Assembly version change in this branch.

## Structured Errors

Structured result conventions will be explicit nominal enums over this payload
model. They do not add generics, exceptions, unwinding, `?`, or implicit
propagation. Multi-cell structured results may exist in locals, parameters,
branches, loops, and match arms, but cannot be returned by the current scalar
ABI.
