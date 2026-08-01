# ADR-0021: Enum Payload Layout Requires Public Architecture Decision

Status: Proposed

## Context

Milestone 1.05 asked whether S3 can add fixed-layout enum payloads and
structured errors on top of the current language-composition campaign.

The current implementation has a deliberately narrow enum model:

- `EnumVariant` stores only a variant name;
- grammar accepts `enum-variant = identifier, NEWLINE`;
- semantic analysis assigns each variant a deterministic `tryte` discriminant;
- enum construction is `Enum.Variant`;
- enum values lower to one existing scalar `tryte` register;
- enum `match` checks exhaustiveness and duplicate arms but has no payload
  binding form;
- imported enums preserve nominal identity and discriminant order;
- native x86-64 receives the same scalar discriminant.

Payload enums would require a value that is both a tag and a payload. Payloads
requested for 1.05 include `trit`, `tryte`, no-payload enum, acyclic record,
nested record, and fixed-capacity static text. Some of those payloads contain
multiple scalar leaves.

## Decision

Do not implement enum payloads in the current branch until a public architecture
decision defines:

- source syntax for payload variants and construction;
- source syntax for match payload bindings;
- whether enum payload layout is represented as tag-first, payload-first, or a
  different canonical form;
- how `SemanticModel.record_leaves()` or a sibling canonical layout API should
  represent tag plus payload without creating a parallel flattening model;
- whether payload-carrying enum values can appear in parameters, locals,
  records, nested records, and imported modules under the current scalarized
  internal ABI;
- whether any payload enum return is allowed, and if so only when the total
  observable layout is one scalar;
- diagnostics for missing, extra, or wrong payloads;
- match exhaustiveness and duplicate-arm behavior when payload bindings are
  present;
- public compatibility impact on grammar, AST, semantic model, IR JSON,
  Assembly, native ABI, golden artifacts, and tooling.

The existing scalar return convention remains unchanged:

- IR: one `RETURN` operand;
- S3 Assembly: one `TRET` operand;
- native x86-64: one result through `rax`.

This ADR explicitly rejects hidden return pointers, multi-register returns,
stack return areas, implicit packing, truncation to the tag, and truncation to
the first payload leaf as part of this campaign.

## Consequences

- No runtime implementation for enum payloads is added in this unit.
- Structured result conventions built on payload enums are blocked until the
  payload layout decision is accepted.
- A minimal xfail test documents the intended user-facing capability without
  making CI red while the architecture remains undecided.
- Milestone 1.05 cannot complete as an implementation milestone in this branch.
- Milestone 1.06 should not proceed because its structured-result candidates
  depend on the blocked 1.05 model.

## Required Follow-Up

Before implementation resumes, create an accepted ADR or equivalent milestone
specification that settles the syntax, layout, binding, diagnostics, and public
format impacts listed above.
