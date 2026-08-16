# M1.39-A Dynamic Buffer Architecture Closure

```text
CAMPAIGN_ID=S3-M139-A
MODE=ARCHITECTURE_AND_SPEC_ONLY
BASE_SHA=c3752f0a5291d5be1bf6d9caebf4d7786b59cfd0
IMPLEMENTATION=NOT_STARTED
M139A_STATUS=ARCHITECTURE_CLOSED
```

## BLOCKER_FROM_PREVIOUS_CAMPAIGN

The prior autonomous campaign stopped at M1.39 because the roadmap did not
define ownership, allocation, lifetime, aliasing, source syntax, error
transport, IR, or native ABI. This campaign resolves those questions and does
not implement any executable behavior.

## CURRENT_FOUNDATIONS

The actual base contains:

- static frame-local memory and static arrays;
- checked half-open slice ranges from M1.33;
- scalar-only FFI from M1.34;
- tagged scalar `DynamicValue` from M1.35;
- existing source `&`/`&mut` reference AST and conservative alias effects;
- deterministic hosted/native limits and Linux x86-64 private addresses.

The base does not contain the previously assumed `OwnedBuffer`, `DynamicBytes`,
`DynamicText`, or public `Allocator` contracts. M1.39 is the first source
contract for them.

## OPTIONS_EVALUATED

| Option | Summary | Result |
| --- | --- | --- |
| A | Move-only owned `bytes`/`text`, lexical borrows, compiler drops, explicit reserve. | **Selected**: best safety/determinism/application/self-hosting balance without generics or GC. |
| B | Explicit integer-like handles and manual destroy. | Rejected: weak use-after-close safety and too much caller discipline. |
| C | Reference-counted shared buffers. | Rejected: hidden destruction, cycles, and less deterministic resource policy. |
| D | Copy-on-write immutable buffers. | Rejected: hidden sharing and mutation/FFI complexity. |

The numeric score matrix and decision-quality records are in ADR-0027.

## SELECTED_ARCHITECTURE

M1.39 introduces ordinary move-only owned values `bytes` and `text`. A value
owns one private allocation. Assignment, parameter passing, and return transfer
the one owner. Deep copy is explicit. `&T` and `&mut T` are non-owning lexical
borrows and do not become machine `noalias` promises.

## PUBLIC_TYPE_MODEL

Exactly `bytes`, `text`, `&bytes`, `&mut bytes`, `&text`, and `&mut text`. No
generic-looking buffer syntax is introduced. Numeric dynamic collections belong
to M1.40.

## PUBLIC_SYNTAX

```s3
fn inspect(value: &bytes) -> i64:
    return bytes_len(value)

fn add_mark(value: &mut bytes):
    bytes_push(value, 33)

fn build() -> bytes:
    mut value: bytes = bytes_new(8)
    bytes_push(&mut value, 65)
    bytes_reserve(&mut value, 16)
    bytes_push(&mut value, 66)
    return value
```

The complete constructors and text functions are normative in
`spec/dynamic-buffers.md`. Methods such as `value.push()` are not introduced;
the existing source language uses named calls and explicit reference arguments.

## OWNERSHIP

One owner, move on assignment/parameter/return, explicit deep clone, no owned
values in records/static arrays/enums in M1.39, and no ownership transfer to C.

## MOVE_SEMANTICS

The source binding is unavailable after a move. SSA consumes one owner and
produces one owner. A moved value cannot be read, borrowed, dropped, or
returned. CFG joins require the same ownership state on every predecessor.

## BORROW_SEMANTICS

Shared borrows may coexist. One mutable borrow excludes all other borrows.
Borrow locals last through their lexical block; temporary call borrows last
through the call. A borrow cannot escape a local owner. M1.39 has no element
reference and no borrowed subslice type.

## ALIASING

The compiler rejects owner move/drop/reserve/push/append/indexed write while an
incompatible borrow is live. This is a source capability rule, not a blanket
Rust-style backend no-alias promise. Foreign callers must not retain or mutate
borrowed C views.

## ALLOCATION

One target-provided allocator is used implicitly by explicit constructors,
reserve, clone, and concat. Capacity is exact. `reserve` is explicit. Push and
append trap when capacity is insufficient instead of silently growing. No user
allocator API is added.

## LIFETIME

Allocation begins at construction or an allocating operation. Valid use ends at
move, scope cleanup, or return transfer. A borrow begins at `&`/`&mut` and ends
at lexical scope end or call return. Reserve/reallocation is forbidden while a
borrow exists. A local-owner borrow cannot be returned.

## DESTRUCTION

The compiler inserts `BUFFER_DROP` at normal lexical exits, branch exits, loop
exits, `break`, and `continue` according to ownership SSA. A return transfers
the returned owner. A terminating runtime trap relies on process reclamation;
no post-trap destructor order is promised.

## TEXT_MODEL

`text` is valid UTF-8 without NUL termination. Length/capacity and search
offsets are bytes. There is no direct code-point indexing. Slices require
code-point boundaries. Arbitrary bytes convert to text only after validation.

## ERROR_MODEL

Compile-time ownership/borrow/type errors use the specified semantic diagnostic
codes. Bounds, capacity, allocator, octet-range, full-buffer, invalid-UTF8, and
text-boundary failures are deterministic runtime traps in M1.39. M1.42 may add
explicit structured result wrappers later; it does not redefine ownership.

## IR_MODEL

Buffers remain one logical typed IR value with ownership state. The semantic
operation family is `BUFFER_ALLOC`, `BUFFER_DROP`, `BUFFER_LEN`,
`BUFFER_CAPACITY`, `BUFFER_LOAD`, `BUFFER_STORE`, `BUFFER_PUSH`,
`BUFFER_RESERVE`, `BUFFER_CLONE`, `BUFFER_SLICE_COPY`, `BUFFER_CONCAT`, and
`BUFFER_UTF8_VALIDATE`. Public IR must version the value/op family and never
serialize a Python object or untyped host pointer.

## SSA_MODEL

Moves consume owners; clones create owners; drops consume owners; joins require
identical availability; loops require stable owner state at the backedge;
returns consume returned owners. Conservative rejection is required when proof
is unavailable.

## RUNTIME_LAYOUT

Logical descriptor: private storage identity, `i64 length`, `i64 capacity`, and
kind. Native storage may use base pointer plus length/capacity and allocator
metadata. Identity and address are non-semantic.

## NATIVE_ABI

S3 internal descriptor order is `(base, length, capacity)` under the existing
private aggregate/sret mechanism. C sees no owned descriptor.

## FFI

Only borrowed `(base_address, i64 length)` views are exposed for `&bytes` and
`&text`. C may read only during the call, may not retain/free/mutate shared
storage, and receives no NUL guarantee. Ownership never crosses FFI.

## DETERMINISM

Exact capacities, explicit active limits, non-semantic addresses, no implicit
growth, stable byte/text results, and no allocator/hash/address identity in
program-visible state.

## CROSS_MODULE

Owned and borrowed bytes/text are valid in exported/imported S3 function
parameters and returns according to move/borrow type. They are not valid inside
records, arrays, or enum payloads in M1.39.

## NEGATIVE_CONTRACTS

| Invalid case | Classification |
| --- | --- |
| use after move | compile-time error |
| local borrow escape | compile-time error |
| incompatible borrow overlap | compile-time error |
| owner operation while borrowed | compile-time error |
| out-of-bounds | deterministic runtime trap |
| capacity overflow/active-limit excess | deterministic runtime trap |
| allocation rejection | deterministic runtime trap |
| full push/append | deterministic runtime trap |
| invalid UTF-8 | deterministic runtime trap |
| interior UTF-8 slice | deterministic runtime trap |
| nested owned value/generic buffer/raw pointer | compile-time unsupported contract |

## M1.40_BOUNDARY

M1.40 may add closed numeric dynamic collections and their growth policy using
the M1.39 owner/borrow/drop contract. It owns `trit`, `tryte`, `i64`, and `f64`
dynamic element families, not M1.39. It may not add maps, generic syntax,
structured results, resource handles, or silently change bytes/text ownership.

## IMPLEMENTATION_GATES

| ID | Gate |
| --- | --- |
| M139-G01 | parser accepts the exact bytes/text declarations and calls; unsupported generic/pointer syntax is rejected |
| M139-G02 | semantic move/use-after-move and lexical borrow negatives produce the specified diagnostics |
| M139-G03 | shared/mutable overlap and reserve/push while borrowed are rejected |
| M139-G04 | constructors, exact capacity, clone, concat, and explicit reserve preserve owner state |
| M139-G05 | bounds, octet, capacity, allocation, full, UTF-8, and boundary traps are deterministic |
| M139-G06 | bytes/text operations pass hosted O0/O1 observable equivalence |
| M139-G07 | bytes/text operations pass Linux x86-64 native round trips |
| M139-G08 | hosted/native and Python oracle differential corpus agrees |
| M139-G09 | cross-module owned return/parameter moves and borrowed calls are verified |
| M139-G10 | borrowed C views are exactly base/length, read-only, non-retaining, and ownership stays in S3 |
| M139-G11 | IR verifier rejects invalid owner joins/drops and deterministic serialization excludes addresses |
| M139-G12 | allocation limits and failure injection leave no partially initialized owner |

## OPEN_QUESTIONS

None for the M1.39 contract. Implementation may choose private backend data
structures and exact Assembly spellings only within the normative logical
rules. Any change to ownership, allocation, borrow, error, syntax, IR logical
shape, or ABI requires a new ADR.

## FINAL_DECISION

`M139A_STATUS=ARCHITECTURE_CLOSED`

`M139A_FINAL_DECISION=SAFE_TO_IMPLEMENT_M1.39_IN_A_SEPARATE_CAMPAIGN`
