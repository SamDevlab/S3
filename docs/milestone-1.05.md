# Milestone 1.05 - Fixed-Layout Enum Payloads and Structured Errors

Status: Blocked - architectural decision required

Milestone 1.05 was audited after the completion of acyclic nested records and
fixed-capacity static text values. The audit found that payload enums cannot be
implemented safely in this branch without a public syntax and layout decision.

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

## Gate

[ADR-0021](decisions/ADR-0021-enum-payload-layout-gate.md) records the required
architecture decision. The branch includes a minimal xfail test,
`tests/test_enum_payload_architecture_gate.py`, showing the intended `Result`
flow that cannot be accepted until syntax and layout are decided.

## Required Decisions

An accepted follow-up must define:

- payload variant declaration syntax;
- payload construction syntax;
- match binding syntax;
- canonical tag and payload leaf order;
- relationship to `SemanticModel.record_leaves()` or a new single canonical
  composite layout API;
- parameter/local/record/module behavior;
- return eligibility under the scalar return convention;
- diagnostics for missing, extra, and wrong payloads;
- exhaustiveness and duplicate-arm rules with bindings;
- public compatibility impact for grammar, AST, IR JSON, Assembly, native ABI,
  goldens, baselines, and tools.

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

Structured result conventions built on payload enums are blocked by the same
decision. S3 can continue to use existing no-payload enums and records
separately, but a nominal `Result.Ok(value)` / `Result.Err(error)` model needs
the payload enum layout before it can be implemented or validated natively.
