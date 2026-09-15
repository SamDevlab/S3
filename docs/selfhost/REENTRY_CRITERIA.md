# Self-hosting re-entry criteria

Self-hosting is currently deferred. Re-entry is design-first and requires a new,
explicit user/project decision. No milestone, version number, or language feature
automatically authorizes another implementation generation.

`SELFHOST_REENTRY_AUTOMATIC=NO`

`STAGE1_V4=NOT_AUTHORIZED`

## Gate 1 — Stable required language subset

Identify the exact Stage1 language subset the compiler itself needs. The subset
must be stable enough that the compiler architecture is not chasing frequent
semantic redesign.

## Gate 2 — S3 representability matrix

Before implementation, every core compiler structure must have an explicit S3
representation and complexity model.

At minimum cover:

- source view / bounded source transport;
- `Token`;
- AST/HIR node representation;
- `ScopeId`;
- `DeclarationId`;
- `TypeId`;
- `FunctionId`;
- `StorageId`;
- `BlockId`;
- `ValueId`;
- `InstructionId`;
- record and enum metadata;
- IR instruction storage;
- verifier state;
- emitter/output state;
- whole-program compiler context.

For each structure document:

- concrete S3 representation;
- mutability model;
- capacity/growth model;
- ownership/reference requirements;
- copy behavior;
- expected asymptotic work;
- failure behavior at capacity boundaries.

If a required structure cannot be represented cleanly, implementation does not
start.

## Gate 3 — One generic compiler pipeline

A complete design must exist for:

```text
source
  -> lexer
  -> parser
  -> generic AST/HIR
  -> semantic passes
  -> generic IR
  -> verifier
  -> emitter
  -> compile_program
```

Production behavior must not depend on feature-slice IDs, milestone IDs,
fixture names, known source positions, or expected outputs.

## Gate 4 — Generic composition root exists on paper first

`compile_program` must be designed before implementation begins. Define:

- inputs;
- outputs;
- state ownership;
- module/program orchestration;
- phase boundaries;
- error propagation;
- deterministic ordering;
- output transport.

The composition root must call generic compiler subsystems, not duplicate them.

## Gate 5 — Structured syntax model is complete for Stage1

The parser representation must be able to encode arbitrary programs in the
required Stage1 subset. Prefer integer IDs/arenas/parallel arrays or another
explicitly self-host-representable form over host object graphs.

The design review must show how nested expressions, blocks, control flow,
records, enums, calls, arrays/references, and source spans compose without
fixture-specific structures.

## Gate 6 — Semantic arena design

Design stable identity and lookup before implementation:

- lexical scopes;
- nearest-visible declaration rules;
- shadowing and scope exit;
- function isolation;
- nominal type identity;
- call target identity;
- storage/mutability association.

Ordinary lookup must not require repeated full-prefix source scans.

## Gate 7 — IR completeness map

Before broad parser work, map every required Stage1 language operation to one or
more generic IR operations.

The map must include control flow, calls, scalar operations, storage, records,
enums, arrays/references, and any other operation used by the compiler source.

No placeholder IR family may stand in for an unknown future design.

## Gate 8 — Verifier plan

For every planned IR family, define independent verifier invariants. The design
must cover duplicate IDs/producers, invalid operands, invalid storage/blocks,
terminators, call signatures, and aggregate metadata where applicable.

## Gate 9 — Emitter plan

Every planned IR operation must have an output encoding strategy before the
frontend is considered architecturally complete. Define output buffering or
streaming, deterministic ordering, capacity behavior, and fail-closed handling
for unsupported IR.

## Gate 10 — Transaction and allocator model

Define deterministic direct allocators for compiler identities. Define
checkpoint/commit/rollback for speculative lowering. Source recounting to
reconstruct IDs is not acceptable.

## Gate 11 — Complexity budget

The architecture review must provide expected complexity and bounded scaling
probes for critical operations. It must exclude by construction:

- repeated whole-function lookup scans;
- ID reconstruction by source recount;
- whole-program reparsing per function;
- layout reconstruction per aggregate access;
- pathological aggregate/compiler-state copying;
- emitter rescans proportional to already-emitted output.

## Gate 12 — Bootstrap boundary

Define before coding:

- Stage0 reference compiler role;
- initial Stage1 artifact;
- true Stage1 self-compilation action;
- next-stage artifact;
- exact Stage2 execution boundary;
- allowed host harness responsibilities.

During true self-compilation the host may mechanically transport bytes, invoke
the compiler, capture output, hash results, and control resources. It may not
perform semantic compiler work.

## Gate 13 — Vertical slices are acceptance only

Vertical slices may be used to validate the generic architecture early, but
slice identity must never become production dispatch. Each slice must exercise
the same generic parser, semantics, IR, verifier, emitter, and composition root.

## Gate 14 — Anti-specialization review

Before implementation authorization, explicitly answer:

- Can two previously unseen supported features be freely composed without a new
  production path?
- Can a new function body be compiled without adding fixture-specific code?
- Can the compiler process a multi-file program through the same entry point?
- Is the number of production paths driven by generic node/IR kinds rather than
  test cases?

A negative answer blocks re-entry.

## Gate 15 — Authorization

Only after Gates 1–14 pass may the project propose a new self-host
implementation. That proposal must be reviewed separately and explicitly
authorized.

Passing these gates does not itself create or authorize "V4".

## Timing policy

There is intentionally no milestone-based automatic restart. Earlier roadmap
capabilities such as borrowed slices and owned dynamic data already exist in the
project and did not, by themselves, resolve the compiler-architecture problem.
Future language/runtime work may improve representability, but re-entry depends
on the architecture evidence above, not on reaching a version number.
