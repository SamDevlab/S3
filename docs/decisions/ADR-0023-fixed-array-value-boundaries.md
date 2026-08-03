# ADR-0023 - Fixed-Array Value Layout And Function Boundaries

Status: Accepted

## Context

S3 already has source syntax for fixed arrays, compile-time lengths, array
literals, indexed reads and writes, local frame memory, bounds checks, and
hosted/native execution. The existing contract deliberately keeps every array
as a local memory object. Arrays cannot appear in function signatures, record
fields, or enum payloads, and they cannot be copied or returned as values.

Milestone 1.07 established `SemanticModel.fixed_value_layout(...)` as the
canonical description of scalarizable fixed-layout values. Milestone 1.08 and
S3 IR/Assembly 0.6 established ordered argument cells, ordered result groups,
group-level discard, hosted tuple transport, and the internal native hidden
sret convention for results wider than one cell. Fixed arrays can reuse these
contracts without adding source pointers, heap allocation, dynamic capacity,
or a parallel array ABI.

Milestone 1.12 needs fixed arrays to cross function and nominal-value
boundaries for later bounded text and self-hosted frontend components. The
architecture must preserve the current mutable local-memory behavior while
making boundary values explicit, deterministic copies.

## Decision

S3 fixed arrays become first-class fixed-layout values. The initial value
domain is deliberately narrow:

- element type is exactly `trit` or `tryte`;
- length is a positive compile-time integer from 1 through 365 inclusive;
- source syntax remains `trit[N]` or `tryte[N]`;
- literal syntax remains `[element0, element1, ...]`;
- nested arrays, arrays of static text, arrays of records, and arrays of enums
  remain unsupported;
- dynamic arrays, dynamic capacity, slices, source pointers, references, and
  aliasing remain unsupported.

An array is one logical source value with an ordered scalar-cell layout. Its
cells are ordered by increasing index. Passing, returning, assigning, or
embedding an array copies every cell by value. No source operation can observe
the address used by a local memory object or by a native backend temporary.

## Source Syntax And Type Identity

No grammar change is required for array types. The existing type production
already parses `element[N]`, and the semantic restrictions above continue to
reject nested forms.

Array type compatibility is structural only within this bounded array domain:

- element types must be identical;
- lengths must be identical;
- `trit[4]` and `tryte[4]` are different types;
- `tryte[4]` and `tryte[5]` are different types.

Array literals continue to require exactly the declared number of elements.
Each element is checked against the declared element type. A literal or other
array value must be complete; there is no partial initialization or implicit
padding.

## Canonical ValueLayout

`SemanticModel.fixed_value_layout(...)` is the only source of array width,
cell types, order, and paths. `ValueLayoutKind` gains a fixed-array kind. For
an array of length `N`, the layout contains exactly `N` cells:

```text
index0
index1
...
index(N-1)
```

Each path is represented using the existing tuple-of-string path model. The
canonical spelling is `("index0",)`, `("index1",)`, and so on. The path is a
semantic identity and diagnostic aid; it is not a memory address or public
offset.

Every cell has the declared scalar element type. Width is checked before any
lowering. A zero length, a length greater than 365, a non-constant length, an
unsupported element type, a nested array, a recursive layout, or a width that
cannot fit the compiler's fixed-layout limits is rejected semantically.

When an array appears in a record field, its index paths are prefixed by the
record field path. For example, field `bytes: tryte[3]` contributes:

```text
bytes.index0
bytes.index1
bytes.index2
```

When an array appears in an enum payload field, the enum remains tag-first.
The payload array cells participate in the existing maximum payload-slot
layout in increasing index order. Inactive payload slots retain the existing
deterministic zero-equivalent initialization contract.

Arrays of nominal values and nested arrays are not required by Milestones
1.13-1.16 and remain outside this decision. They may be considered only when
they can reuse this same `FixedValueLayout` recursively without a second
layout system.

## Mutability And Local Storage

Mutability belongs to a binding, not to an array value or an address.

- a mutable local array may continue to use one typed IR memory object;
- indexed assignment mutates only that local binding;
- an immutable local array may be represented by memory or scalar registers as
  an implementation choice, provided behavior and initialization checks remain
  identical;
- parameters are immutable bindings under the existing language rule;
- copying a mutable local array into another binding or across a call copies
  all current cells and creates no alias;
- whole-array assignment is allowed only when the target binding is mutable and
  both complete array types match exactly.

The compiler must evaluate the source array value once, then materialize or
copy the complete ordered cell group. It must not duplicate a source call or
re-evaluate element-producing expressions while copying a previously formed
array value.

## Parameters And Calls

An array parameter expands to its canonical ordered cell sequence in IR and
Assembly function parameter lists. A source call still has one argument for
the array. Lowering expands that argument to the full scalar group exactly
once.

The existing internal argument convention is reused:

- cells are passed in increasing index order;
- multiple array and scalar arguments retain source argument order;
- arrays wider than the available native argument registers naturally continue
  into the existing stack-argument path;
- if the callee also has an aggregate result, the hidden sret physical argument
  is inserted first and every user argument cell shifts according to the
  existing aggregate-result ABI;
- no partially passed array group is valid.

The callee receives independent scalar parameter cells. Reconstructing a local
memory object for indexed access is allowed, but that object is callee-owned
and cannot alias caller storage.

## Results And Discard

An array result is one logical source result whose IR and Assembly result group
contains every canonical array cell.

- width one uses the existing scalar return path and native `rax` convention;
- width greater than one uses the existing ordered result group and hidden
  native sret convention from ADR-0022;
- callers allocate all destination cells before emitting one call;
- callees emit one return with the complete ordered operand group;
- recursion and nested calls use independent caller-owned native result areas;
- ignoring an array result discards the complete result group while preserving
  exactly-once call execution;
- partial result use, a missing cell, an extra cell, or cell reordering is
  invalid.

The entry function `main` remains scalar-only. An array return type for `main`
is rejected with the existing aggregate-entry diagnostic contract.

## Records And Enum Payloads

Fixed arrays of `trit` or `tryte` are permitted as record fields and enum
payload fields. Their cells are incorporated directly into the enclosing
canonical layout. There is no hidden Python array object, secondary leaf list,
or emulator-only metadata.

Record construction, enum construction, field extraction, match payload
binding, copy, parameter passing, and return lowering must consume the same
layout paths. A complete embedded array may come from an exact-type array value
or a complete literal accepted by the existing initializer syntax. Partial
field or payload arrays are rejected.

Nominal record and enum identity remains `ModuleId + TypeName`. Embedding an
array does not make the enclosing nominal type structural. Imported and
qualified signatures use the owner module's canonical nominal layout and the
same structural array element/length contract.

## IR And Assembly

No format bump is required. S3 IR 0.6 and S3 Assembly 0.6 already represent all
required information as ordered scalar parameters, result types, call argument
groups, call destination groups, return operand groups, and typed memory
objects.

Source arrays do not introduce an IR array type. At boundaries they are
scalarized according to `FixedValueLayout`; for local mutable storage they use
the existing typed `IRMemoryObject`, `LOAD`, and `STORE` instructions. The
source type and layout are compiler semantic data, not a new serialized runtime
object.

The 0.5 readers remain width-one compatibility readers. Existing 0.5 artifacts
do not gain a source-array boundary encoding. New compiler output continues to
use 0.6 whenever multi-cell groups are present.

## Verifier, Optimizer, And SSA

The verifier continues to operate on flattened typed scalar contracts. It must
validate:

- argument count and type against the fully expanded callee parameters;
- result count and type against the callee result group;
- return count and type against the current function result group;
- declaration/definition and imported-signature agreement;
- complete call destination groups and complete return groups;
- no missing, extra, duplicated, or partially discarded cells.

Array element count and source array type equality are semantic checks before
lowering. The verifier does not infer source arrays from arbitrary neighboring
registers.

Optimizer and SSA passes continue to process scalar cells, while preserving the
existing call result-group invariants. They must not duplicate calls, reorder
cells across a logical group, partially eliminate an observable group, or
invent source aliasing. No new optimizer pass is required.

## Hosted And Native Execution

The emulator uses existing register cells, call argument tuples, result tuples,
memory objects, bounds checks, frame limits, and instruction limits. It does not
store a hidden source-level array object.

The Linux x86-64 backend reuses the existing internal S3 calling convention:

- scalar array cells use the existing physical argument sequence;
- overflow arguments use the existing stack path;
- result width one returns in `rax`;
- result width greater than one uses the existing caller-owned hidden sret
  area;
- nested calls and recursion receive independent temporaries;
- stack alignment and cleanup are computed after inserting hidden sret and all
  expanded user argument cells.

Native pointers used to address stack slots and sret areas remain backend-only
implementation details. They cannot be produced, stored, compared, or observed
by S3 source.

## Diagnostics

Diagnostics must be deterministic and identify the source array type or
canonical path where useful. Required rejection classes include:

- non-positive or over-limit length;
- non-constant length;
- unsupported or nested element type;
- element count or element type mismatch;
- incompatible whole-array assignment;
- incompatible parameter or result type;
- incomplete initialization or return;
- uninitialized element read;
- aggregate `main` result;
- malformed lowered argument or result groups.

Bounds behavior remains unchanged: constant out-of-range indices are semantic
errors; dynamic out-of-range indices fail during hosted or native execution.

## Limits

This decision does not add:

- dynamic arrays or capacities;
- multidimensional or nested arrays;
- arrays of static text, records, enums, or arrays;
- heap allocation or garbage collection;
- pointer, reference, borrowing, address-of, or slice syntax;
- source aliasing;
- public C ABI compatibility;
- a new IR or Assembly version;
- default self-hosted compiler components.

The maximum length remains 365, matching the existing positive tryte-indexed
array contract. Wider aggregate groups are bounded by existing compiler frame,
instruction, and artifact limits.

## Alternatives Considered

### Pass Local Memory Addresses

Rejected. It would expose aliasing and pointer semantics at source boundaries,
make mutability non-local, and create a second ABI beside fixed value groups.

### Add An IR Array Value Type

Rejected for this milestone. Ordered scalar groups and typed local memory
already express every required behavior. A new serialized type would force a
format bump without adding semantic capability.

### Copy Through Hidden Python Objects

Rejected. It would make Python object identity part of lowering or emulator
behavior and would not be reproducible across hosted and native execution.

### Keep Arrays Local-Only

Rejected. Bounded text and self-hosted tokenizer/parser components require
fixed ordered values to compose across modules and function boundaries.

## Consequences

Positive:

- arrays join the same canonical fixed-layout system as scalars, records, and
  enums;
- boundary behavior is copy-by-value and independent of local storage choice;
- IR, Assembly, emulator, optimizer, SSA, and native result transport are
  reused without a format bump;
- the design provides bounded ordered storage for later self-hosting stages.

Costs:

- semantic analysis and lowering must distinguish complete array values from
  indexed scalar expressions;
- mutable local memory must be flattened when crossing a boundary and rebuilt
  when a callee needs indexed access;
- record and enum layout helpers must recurse into array fields through the
  canonical layout;
- tests must cover wide argument groups, hidden sret interaction, recursion,
  imports, O0/O1, emulator, and native parity.

## Testing Strategy

Coverage must include, after the campaign-wide implementation gate opens:

- `trit` and `tryte` parameters and results at widths 1, 2, 3, 8, and beyond
  available native argument registers;
- exact length and element-type mismatch diagnostics;
- immutable and mutable local copies with no aliasing;
- whole-array assignment and complete initialization;
- records and enum payloads containing arrays;
- imported and qualified nominal signatures;
- nested calls, recursion, multiple array parameters, aggregate result plus
  array parameters, and ignored array results;
- verifier rejection of partial argument/result groups;
- O0/O1, emulator, and Linux x86-64 parity;
- constant and dynamic bounds failures;
- aggregate `main` rejection;
- deterministic lowering under source-unit permutations.
