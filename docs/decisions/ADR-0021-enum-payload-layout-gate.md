# ADR-0021: Enum Payload Layout Requires Public Architecture Decision

Status: Decision required

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

The current IR has one value in each `RETURN`, one typed destination for scalar
operations, and no aggregate value object. The current S3 Assembly has one
`TRET` operand and no public instruction for carrying a tag with a payload. The
native x86-64 backend mirrors that scalar result through `rax`; it has no hidden
return pointer, stack return area, or multi-register result convention. The
verifier, SSA optimizer, emulator, renderer, and JSON/Assembly serializers all
assume that the observable value crossing these boundaries is one typed scalar
unless records are already flattened in an internal, non-versioned position.

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

## Architectural Impact

- Verifier: must know whether a payload enum is one scalar, several internal
  cells, or a versioned aggregate value. It cannot validate tag/payload arity
  by looking only at the current scalar enum type.
- Optimizer and SSA: must preserve tag and payload dominance, copies, dead-code
  behavior, equality boundaries, and match selection without separating a tag
  from a still-live payload.
- Emulator: must store and compare payload enum values without inventing an
  emulator-only representation that the IR, Assembly, and native backend cannot
  share.
- Native x86-64 backend: must lower locals, parameters, branches, and allowed
  returns without silently changing the public ABI.
- Renderer: must render any new IR or Assembly shape deterministically, and the
  rendered artifact must remain compatible with the declared Assembly version.
- Versioned formats: grammar, AST shape, IR JSON, S3 Assembly, diagnostic
  schema, goldens, and tooling must either remain unchanged by construction or
  receive an explicit compatibility/versioning decision.

## Alternatives Considered

### 1. Multiple internal cells while preserving scalar returns

Represent a payload enum in supported non-return positions as a deterministic
sequence of internal cells: tag plus payload leaves. This follows the existing
record scalarization style and can reuse a canonical layout query shared with
`SemanticModel.record_leaves()` or a sibling API.

Consequences:

- keeps public IR and Assembly versions stable if the representation never
  appears as a new public aggregate value;
- works naturally for locals, parameters, records, modules, and match lowering;
- still cannot return multi-cell payload enums under the current scalar return
  convention;
- needs explicit diagnostics for return rejection and for payload arity/type
  errors.

### 2. New aggregate value in IR and Assembly

Introduce a first-class tag-plus-payload aggregate in IR JSON and S3 Assembly.
The verifier, renderer, parser, emulator, optimizer, and native backend would
all understand that aggregate directly.

Consequences:

- gives enum payloads a public, explicit representation;
- may unlock future aggregate returns and richer structured diagnostics;
- requires versioned public format changes, new verifier rules, renderer
  updates, golden updates, and backend ABI decisions;
- is too broad to select silently inside the current composition campaign.

### 3. Compact encoding for limited payloads

Pack selected tag/payload combinations into one existing scalar when the full
state space fits, for example only small no-payload or single-small-scalar
cases.

Consequences:

- preserves the one-scalar return path for a narrow subset;
- creates special cases that do not generalize to nested records or fixed text
  handles;
- risks surprising truncation, range pressure, and non-uniform diagnostics;
- should only be accepted with an explicit compatibility contract and clear
  rejection rules for unsupported payload shapes.

### 4. Defer until a versioned ABI/IR campaign

Do not implement payload enums now. Open a dedicated architecture campaign to
settle syntax, tag/payload layout, return eligibility, verifier and optimizer
rules, emulator/native behavior, renderer impact, and public versioning.

Consequences:

- preserves all current public formats and ABI contracts;
- avoids emulator-only or backend-only behavior;
- delays structured results and Milestone 1.06 candidates that depend on them;
- is the selected state of this branch: decision required before implementation.

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
