# ADR-0022 - Aggregate Function Results

Status: Accepted

## Context

S3 currently represents every function result as exactly one scalar cell.
Source-level records and payload enums may already have fixed multi-cell layouts
in locals, parameters, branches, loops, matches, and module calls, but semantic
analysis still rejects multi-leaf records and multi-cell enums as direct return
types.

The current implementation is width-1 throughout the pipeline:

- `IRFunction.return_type` stores one `IRType`;
- `IRInstruction.result` stores at most one destination register;
- `IROpcode.CALL` defines one result register;
- `IROpcode.RETURN` consumes one operand;
- `.function name -> type` stores one Assembly return type;
- `TCALL` has one destination register before the callee;
- `TRET` has one source register;
- the verifier checks one call result and one return operand;
- the emulator transports one return value through each call frame;
- the Linux x86-64 backend returns one physical value in `rax`.

Milestone 1.07 introduced a canonical semantic fixed value layout. Milestone
1.08 uses that layout to define how one source-level value can cross a function
boundary when it contains more than one scalar cell.

## Decision

S3 will represent aggregate function results as an ordered list of result cells
in IR and S3 Assembly. A source function still returns one logical value. The
multi-cell representation is internal to the compiler formats and execution
engines.

The selected architecture is:

- source: one return expression with one declared return type;
- semantic: result width and cell types are derived from `FixedValueLayout`;
- IR: function result layout is an ordered tuple of result cell types;
- IR `CALL`: defines an ordered tuple of destination registers;
- IR `RETURN`: consumes an ordered tuple of source registers;
- Assembly: function signatures, `TCALL`, and `TRET` encode ordered cell lists;
- emulator: transports an ordered tuple of cells between frames;
- native x86-64: width 1 keeps the existing `rax` path;
- native x86-64: width greater than 1 uses an internal hidden sret area owned by
  the caller and written by the callee;
- source language: no pointer type, no heap object, no tuple return, no variadic
  return, and no visible sret parameter are introduced.

## IR Model

IR JSON must move to version `0.6.0` for new writers.

`IRFunction` gains a result layout equivalent to:

```text
result_types: tuple[IRType, ...]
```

Compatibility rule:

- 0.5.0 functions are normalized as `result_types = (return_type,)`;
- width 1 may continue to expose `return_type` as a compatibility property;
- width 0 is invalid for source functions;
- width greater than 1 must not be serialized as 0.5.0.

`CALL` gains ordered result registers:

```text
results: tuple[int, ...]
callee: str
operands: tuple[int, ...]
```

`RETURN` uses `operands` as the ordered return cell list. For all functions, the
operand count must equal the function result width and each operand type must
match the corresponding result type.

A call whose result is ignored must still be represented as a full result group
with either explicit discarded destinations or a verifier-visible discard marker
chosen during implementation. Partial result use is invalid.

## Assembly Model

S3 Assembly must move to version `0.6.0` for new writers.

The accepted textual shape uses explicit lists for multi-cell positions:

```s3asm
.s3asm 0.6.0

.function make_pair -> [tryte, tryte]
    .register r1, tryte
    .register r2, tryte
.label entry
    TRET   [r1, r2]
.end

.function main -> tryte
    .register r3, tryte
    .register r4, tryte
    .register r5, tryte
.label entry
    TCALL  [r3, r4], make_pair, []
    TADD   r5, r3, r4
    TRET   r5
.end
```

Compatibility rule:

- 0.5.0 `.function name -> tryte` is normalized to one result type;
- 0.5.0 `TCALL r1, callee, ...` is normalized to one result destination;
- 0.5.0 `TRET r1` is normalized to one return cell;
- 0.6.0 may render width-1 lists as the legacy scalar spelling only when the
  parser and renderer preserve the declared format unambiguously;
- 0.5.0 input containing 0.6.0 list forms is rejected.

The exact renderer spacing remains a deterministic implementation detail, but
the list boundaries are normative.

## Verifier

The verifier must validate:

- function result width is at least one;
- each function result type is known;
- `CALL` result count matches the callee result width;
- `CALL` result register types match result cell types;
- `RETURN` operand count matches the current function result width;
- `RETURN` operand types match result cell types;
- no result cell is omitted or duplicated;
- call arguments still match parameter types;
- all terminators and CFG rules remain valid;
- legacy 0.5.0 artifacts cannot smuggle 0.6.0 result lists.

## Optimizer And SSA

Each result cell is an ordinary scalar SSA value, but cells produced by one call
form one result group. Optimizer passes must preserve that group identity enough
to avoid removing, reordering, or mixing cells independently when doing so would
change the source-level aggregate value.

Side-effect rules are unchanged: calls remain observable and must execute once
unless a later accepted rule proves removal safe.

The current SSA strategy may continue to use phi nodes and out-of-SSA memory for
individual scalar cells. It must not introduce a public tuple type or a hidden
source-level pointer.

## Emulator

The emulator represents call returns as an ordered tuple of scalar cell values.
This tuple is an implementation of the IR result cell list, not an extra hidden
semantic object.

The emulator must preserve:

- exactly-once callee execution;
- frame limits;
- instruction limits;
- recursive frame independence;
- type checks;
- deterministic diagnostics.

## Native x86-64 ABI

The native ABI remains an internal S3 ABI, not a C ABI claim.

For width 1:

- the callee returns the scalar value in `rax`;
- existing argument register and stack argument behavior is preserved.

For width greater than 1:

- the caller allocates a return area in its own frame;
- the caller passes the return area address as an internal hidden first physical
  argument;
- user-visible arguments are shifted after the hidden physical argument;
- stack arguments are recalculated after the shift;
- the callee writes every result cell in canonical order;
- the caller copies every result cell from the return area into destination
  registers;
- recursive calls allocate independent return areas;
- nested calls cannot share a result area unless proven safe by implementation.

The source language never exposes the address and cannot store or compare it.

## Versioning And Migration

New IR JSON and S3 Assembly writers emit `0.6.0` once multi-cell result support
lands.

Readers keep accepting valid 0.5.0 artifacts and normalize them to width 1.
Readers reject unknown future minor versions, incompatible major versions,
malformed result lists, and 0.6.0-only fields under a 0.5.0 header.

Source syntax version remains unchanged because no source grammar is added.

Goldens must be migrated only after the new format is implemented, reviewed, and
proven deterministic.

## Alternatives Considered

### Hidden Return Area In IR

Rejected. It would expose address-like operations too early in the compiler IR,
make the emulator less direct, and force every non-native consumer to model an
implementation detail that only the native backend needs.

### Packing In Physical Registers

Rejected. It has bounded capacity, complicates type handling, does not scale to
nested records or payload enums, and would be a native backend policy rather than
a portable IR and Assembly contract.

### Packing Into One Cell

Rejected. It loses domain information, risks overflow, cannot represent fixed
text handles plus other payload cells safely, and would reintroduce truncation.

### Keep Scalar Returns Only

Rejected for this campaign. It would keep structured result enums and larger
self-hosting components blocked even though fixed value layouts are now
available.

## Consequences

Positive:

- aggregate returns become explicit and verifiable in stable formats;
- width-1 programs keep the existing physical fast path;
- emulator and verifier remain independent from native stack details;
- backend sret is hidden from the language;
- records, nested records, payload enums, and structured result enums can share
  one return mechanism.

Costs:

- IR JSON and S3 Assembly need a coherent version bump;
- parser, renderer, verifier, emulator, optimizer, SSA, and native backend must
  be updated together;
- existing goldens will need a reviewed migration after implementation;
- ignored aggregate call results need an explicit group-level representation.

## Testing Strategy

Required tests:

- legacy 0.5.0 IR and Assembly width-1 reading;
- 0.6.0 IR round-trip with one and multiple result cells;
- 0.6.0 Assembly parse/render with one and multiple result cells;
- verifier width/type mismatches for call and return;
- optimizer/SSA preservation of result groups;
- emulator calls, nested calls, recursion, ignored results, and branches;
- native width-1 preservation in `rax`;
- native width greater than 1 through hidden sret;
- no partial result consumption;
- malformed 0.6.0 list diagnostics;
- 0.6.0 syntax rejected under 0.5.0 headers.
