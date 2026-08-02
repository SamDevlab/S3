# ADR-0021: Fixed Tagged Layout for Enum Payloads

Status: Accepted

## Context

Milestone 1.05 adds payload-carrying enums and structured result conventions
after the language-composition campaign closed Milestones 1.02 through 1.04.
The previous branch stopped because payload enums require a public
representation decision before implementation.

The current no-payload enum model is intentionally scalar:

- AST `EnumVariant` stores only a variant name;
- grammar accepts `enum-variant = identifier, NEWLINE`;
- semantic analysis assigns each variant a deterministic `tryte` discriminant;
- enum construction is `Enum.Variant`;
- enum values lower to one existing scalar `tryte` register;
- enum `match` checks exhaustiveness and duplicate arms but has no payload
  binding form;
- imported enums preserve nominal identity and discriminant order;
- IR, S3 Assembly, emulator, and native x86-64 receive one scalar
  discriminant.

The implementation also has a proven scalarization model for records:

- `SemanticModel.record_leaves()` is the canonical record leaf source;
- record leaves are flattened depth-first in declaration order;
- record parameters expand to multiple scalar IR parameters;
- record values in locals, copies, calls, branches, and O1 SSA are represented
  through existing scalar registers and memory;
- multi-leaf record returns are rejected before lowering because the public
  return convention is one scalar.

The current persistent IR and Assembly formats remain scalar:

- IR JSON version `0.5.0`;
- S3 Assembly version `0.5.0`;
- IR `RETURN` carries one operand;
- S3 Assembly `TRET` carries one operand;
- native x86-64 returns one result through `rax`;
- no hidden return pointer, stack return area, or multi-register return exists.

There is no universal aggregate cell object in the public IR or Assembly.
However, the existing scalar register space already carries `trit`, `tryte`,
closed no-payload enum discriminants, static text handles, and scalarized record
leaves. That is enough for a deterministic internal layout as long as it never
pretends to provide aggregate returns.

## Decision

Payload-carrying enums use a fixed tagged multi-cell layout in all supported
non-return value positions.

The logical cell order is:

```text
tag, payload_cell_0, payload_cell_1, ..., payload_cell_N
```

Rules:

- the tag is always cell 0;
- the tag type is `tryte`;
- tag values are the existing declaration-order enum discriminants;
- payload cells follow the selected variant payload field order;
- record payload fields are scalarized through `SemanticModel.record_leaves()`;
- nested record payloads use the same depth-first declaration order;
- static text payload leaves are scalar string handles;
- no-payload enum payload leaves are `tryte` discriminants;
- payload enum leaves are allowed only when their layout graph is acyclic and
  statically sized;
- the enum type width is fixed and equals `1 + max(payload_leaf_count)`;
- each payload cell position has one canonical scalar slot type for the enum
  type;
- variants whose leaves would require incompatible scalar kinds at the same
  payload cell position are rejected semantically;
- no-payload variants in a payload enum still occupy the enum type's fixed
  width;
- inactive payload slots are deterministically initialized to zero-equivalent
  scalar cells of their canonical slot type;
- implementations must never truncate to the tag or first payload leaf.

The semantic model must expose one canonical enum layout API, sibling to the
record layout API. The names may evolve with implementation, but the API must
answer:

- enum identity;
- variant discriminants;
- payload field names;
- payload leaf paths and scalar types;
- canonical payload slot scalar types;
- fixed cell count;
- tag position;
- inactive slot policy;
- return eligibility.

Lowering, verifier tests, optimizer tests, SSA tests, emulator tests, and native
tests must consume this semantic layout rather than duplicating layout
calculation.

## Syntax Direction

No-payload variants keep the existing spelling:

```s3
enum Status:
    Ready
    Failed
```

Payload variants use named fields:

```s3
enum Result:
    Ok(value: tryte)
    Error(code: tryte, label: string)
```

Construction uses the existing qualified variant surface plus named payload
arguments:

```s3
value: Result = Result.Ok(value=3)
error: Result = Result.Error(code=-1, label="parse")
```

Match labels keep the qualified variant spelling and may bind payload fields:

```s3
match value:
    Result.Ok(value):
        return value
    Result.Error(code, label):
        return code
```

Payload bindings are scoped only to the matching arm.

## Supported Payloads

Initial payloads may contain:

- `trit`;
- `tryte`;
- no-payload enum values;
- acyclic record values;
- nested acyclic record values;
- fixed-capacity static text values;
- payload enum values only when the enum layout graph remains acyclic and
  statically sized.

The implementation must reject:

- recursive payload graphs;
- payload graphs with cycles through records or enums;
- unknown payload types;
- private payload types not visible through the module/import system;
- array payloads;
- payloads without static layout;
- missing payload arguments;
- extra payload arguments;
- duplicate payload arguments;
- payload fields with incompatible types;
- multi-cell enum returns.

## Parameters, Locals, Copies, Branches, and Loops

Payload enum values are first-class in supported non-return positions:

- immutable locals store all cells;
- copies preserve every cell in canonical order;
- function parameters expand to the fixed cells in canonical order;
- caller and callee use the same semantic layout;
- branch and loop joins preserve every live cell through existing scalar
  registers, memory, and SSA phi mechanics;
- no Python object may carry hidden payload state outside the IR-visible cells.

Mutable payload enum bindings are not required by this decision. If the existing
language only supports immutable composite bindings, payload enums follow that
boundary until a later mutability milestone changes it.

## Match

Match dispatch reads only the tag cell.

For the selected arm:

- no-payload variants expose no bindings;
- payload variants expose the requested payload field bindings;
- field bindings are typed according to the variant declaration;
- record and nested-record bindings preserve their scalar leaves;
- fixed text bindings preserve their string handle;
- inactive slots of other variants are not observable through bindings;
- duplicate arms and non-exhaustive matches remain semantic errors.

Fallback arms may remain supported only when consistent with the existing match
rules and binding model. A fallback arm cannot bind payload fields because it
does not identify a specific variant payload shape.

## Return Policy

The public return convention remains scalar.

Payload enum return classification is by enum type width, not by the specific
variant expression:

- no-payload enum types whose layout is exactly one cell may return through the
  existing scalar path;
- any enum type whose fixed width is greater than one is rejected as a function
  return type before lowering;
- returning a no-payload variant of a multi-cell enum is still rejected because
  the type's full fixed layout is multi-cell;
- no implementation may return only the tag, return only one payload leaf,
  compact silently, use a hidden return pointer, use a stack return area, or
  use multiple result registers.

Aggregate returns remain a separate future ABI decision.

## IR, Assembly, Renderer, and Versions

This decision preserves the public IR JSON and S3 Assembly formats by
representing payload enum values as existing scalar cells in positions that
already support scalarized values.

Version policy for this campaign:

- IR JSON remains `0.5.0`;
- S3 Assembly remains `0.5.0`;
- no new public IR opcode is required;
- no new public S3 Assembly opcode is required;
- renderers keep rendering existing scalar instructions;
- goldens change only when the generated scalar instruction sequence for a
  tested source legitimately changes.

If implementation later discovers that a new public aggregate IR/Assembly value
is unavoidable, this ADR must be reopened before that change lands.

## Verifier, Optimizer, SSA, Emulator, and Native Backend

Verifier responsibilities:

- validate scalar instruction types as it does today;
- reject arity/type mismatches introduced by lowering tests and semantic tests
  before malformed payload layouts can reach public artifacts;
- keep return validation scalar.

Optimizer and SSA responsibilities:

- treat each payload cell as an ordinary typed scalar;
- preserve tag and payload cells that are live;
- never remove a payload cell that is used by a later binding;
- never treat inactive slots as semantic payload of a different variant;
- preserve phi arity through the existing one-register-at-a-time SSA model.

Emulator responsibilities:

- execute only the scalar IR/Assembly cells it receives;
- not store stronger hidden enum objects;
- observe the same tag/payload cells as native execution.

Native x86-64 responsibilities:

- preserve parameter expansion order;
- preserve tag and payload cells across calls, branches, and loops;
- preserve scalar return ABI through `rax`;
- reject or avoid any aggregate-return lowering.

## Imports and Nominal Identity

Payload enum identity remains nominal and module-owned:

- identity is still `ModuleId + TypeName`;
- same-name types from different modules remain incompatible;
- same-shape types from different modules remain incompatible;
- imported variants use the defining enum's discriminants and payload layout;
- qualified construction and qualified match labels use the defining type.

Payload field types must be visible and valid under the same explicit import
rules already used for records and enums.

## Alternatives Rejected

### New aggregate value in IR and Assembly

Rejected for this campaign. It would require new public IR/Assembly shapes,
renderer changes, artifact version decisions, verifier changes, and native ABI
work. It may be useful for a future aggregate-return campaign, but payload enums
can be implemented now through existing scalarized positions.

### Packed scalar encoding

Rejected. Packing tag and payload into one scalar cannot represent record,
nested record, static text, or nested payload enum leaves generally. It risks
overflow, range coupling, and variant-specific truncation.

### Variant-specific representation without a uniform value

Rejected. Keeping payload only inside arm-local structures would prevent
payload enums from being first-class locals, parameters, copies, branches, and
loops.

### Deferral until a new ABI/formatted aggregate campaign

Rejected as the default path because the fixed multi-cell model is implementable
without changing the scalar return ABI or public artifact versions. Deferral
remains required only if implementation proves a hidden ABI change is
unavoidable.

## Consequences

- Milestone 1.05 implements payload enum syntax, semantic layout, lowering,
  match payload bindings, structured result conventions, O0/O1, and native
  harness coverage without changing public artifact versions.
- Milestone 1.06 may use structured results only where the result value does
  not need to cross the current scalar return boundary.
- ABI remains unchanged.
- Aggregate returns remain unsupported.
- Python remains the reference compiler and default path.

## Migration Strategy

1. Add AST and parser payload syntax without changing no-payload enum behavior.
2. Add semantic enum layout APIs and cycle detection.
3. Lower payload enum locals, copies, parameters, branches, and match bindings
   through existing scalar cells.
4. Reject multi-cell enum returns before lowering.
5. Validate O0/O1, emulator, and native x86-64 equivalence.
6. Document structured result conventions as explicit match-based flows, with
   no generics, exceptions, `?` operator, or implicit propagation.

## Test Strategy

Coverage must include:

- no-payload enum compatibility;
- scalar payloads;
- no-payload enum payloads;
- record and nested record payloads;
- fixed static text payloads;
- imported payload enums and qualified variants;
- copies, parameters, branches, loops, and match bindings;
- duplicate/non-exhaustive match cases;
- payload arity/type diagnostics;
- recursive payload rejection;
- multi-cell return rejection;
- O0/O1 equivalence;
- native x86-64 harness execution where the host supports it;
- renderer/golden checks for unchanged public format behavior.
