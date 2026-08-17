# Composite Owned Values

Status: normative architecture contract for M1.51. Implementation is not
started by this specification.

## Scope and terminology

An **owned leaf** is one of the closed dynamic value families `bytes`, `text`,
`tryte_vector`, `i64_vector`, `f64_vector`, `i64_map`, or `i64_set`. An
**aggregate** is a record, enum payload, static array, or nested fixed
aggregate. An aggregate containing an owned leaf is one **owned aggregate**.

The ownership unit is the whole aggregate. The language does not expose an
address, allocation token, descriptor pointer, GC handle, reference count, or
type-erased owner.

## Composition

Records may contain owned leaves and nested supported aggregates. Enum payloads
may contain the same. Static arrays may contain supported aggregate elements,
including nested owned aggregates. Dynamic collections whose elements are
arbitrary owned aggregates are not part of M1.51.

Every declared field is initialized exactly once before the aggregate becomes a
public value. Public partial initialization, `MaybeUninit`, and runtime field
bitmasks are forbidden. A failed construction must clean already-created
temporary fields in deterministic reverse order and must not publish a partial
aggregate.

## Logical and physical layout

The logical layout is target-independent:

1. fields follow declaration order;
2. nested aggregates are traversed recursively in declaration order;
3. arrays are indexed in increasing order for layout identity;
4. enums contain the existing discriminant and active-payload layout;
5. ownership metadata is attached to the declared type, never inferred from a
   runtime address.

The physical layout is target-specific. Each field begins at the next offset
that satisfies its target alignment. The aggregate alignment is the maximum
field alignment, and the final size includes deterministic tail padding to
that alignment. Array elements are contiguous at an aligned stride.

For x86-64, each dynamic leaf uses a private `{base,length,capacity}`
descriptor of three 64-bit words, size 24 bytes, alignment 8. The descriptor
is backend storage only. It is not a public pointer, is not comparable by S3
source code, and is not a C ABI record. No outer descriptor wraps the entire
aggregate.

## Function boundaries

An owned aggregate parameter uses an indirect internal ABI. The caller places
the aggregate in backend-owned storage and transfers ownership to the callee.
The source-level signature contains the aggregate type, not a pointer.

An owned aggregate return uses a caller-provided result slot (hidden sret in
the internal backend ABI). The callee writes a complete aggregate into that
slot and transfers ownership to the caller. Width-one scalar returns retain
their existing scalar path. No hidden address is represented in S3 IR as a
source value.

## Ownership operations

### Move

Assignment, parameter transfer, and return move the whole aggregate. After a
successful move the source is semantically unavailable. A runtime moved flag
and zero-after-move are not required. The implementation must reject use,
move, drop, borrow, or replacement of the moved source.

Partial field move is forbidden in M1.51. A field may be projected for borrow
or read according to its declared type, but ownership cannot be extracted from
an aggregate field independently.

### Borrow

Borrowing a field creates a lexical projection tied to the aggregate owner. A
shared projection may coexist with other non-overlapping shared projections. A
mutable projection excludes overlapping shared or mutable projections. An
active field borrow blocks whole-aggregate move and drop. Reallocation or
replacement that could invalidate the projection is forbidden while it is
active. No machine-level `noalias` promise is made.

### Replacement

Owned field replacement has transactional order:

1. evaluate and fully validate the new value;
2. if evaluation succeeds, drop the old field;
3. move the new value into the field.

If evaluation or construction fails before step 2, the old aggregate remains
valid. The replacement operation is never permitted while a conflicting borrow
is active.

### Clone

Clone is explicit and recursively deep. Each owned leaf uses its established
clone contract. `bytes` and `text` preserve exact logical content and their
specified capacity behavior. Vectors, maps, and sets preserve source capacity.
If a destination field has already been created when a later clone fails, the
created destination fields are dropped exactly once in reverse construction
order. The source is unchanged and remains valid.

### Drop

Drop glue is static, compiler-generated, recursive, and exactly once. Records
drop fields in reverse declaration order. Arrays drop elements in reverse index
order. Enums drop only the active payload, after its discriminant identifies
the active variant. Nested aggregates recurse using the same rules.

## Control flow

M1.51 ownership analysis is whole-aggregate. At a CFG join or loop backedge,
all incoming paths must agree on the aggregate's whole-value state. A moved,
borrowed, initialized, or live state may not be silently merged with an
incompatible state.

Field-sensitive path-dependent states, partial field moves, conditional
reinitialization, edge cleanup normalization, and full exactly-once cleanup
proofs at arbitrary exits belong to M1.52. M1.51 does not weaken its whole
aggregate rule to simulate those features.

## FFI and limits

Owned aggregates cannot cross a C boundary in either direction. Existing
scalar FFI and borrowed `bytes`/`text` views remain the only supported foreign
value contracts. Python buffer adaptation remains copying/borrowing behavior;
it is not an ownership transfer.

The existing 64 MiB/default logical resource limits and instruction limit remain
unchanged. M1.51 adds no aggregate-global memory limit, allocator API, implicit
growth policy, GC, refcounting, raw pointer surface, traits, or general
generics.

## Determinism and optimization

Type identity, field order, layout identity, alignment calculations, drop
order, clone order, ownership diagnostics, and IR ownership metadata are
deterministic. They must not include addresses, timestamps, absolute paths,
random hashes, or allocation history.

O0 is the reference semantics. O1 must preserve ownership, borrow, clone, drop,
failure, and observable-result behavior. No ownership-eliding optimization is
authorized by M1.51A.

## Required diagnostics

The implementation should use stable diagnostic identities for at least:

- use after whole-aggregate move;
- move or drop while a field is borrowed;
- unsupported partial field move;
- incompatible ownership state at a CFG join or backedge;
- owned aggregate at a C boundary;
- dynamic collection of an arbitrary aggregate;
- partial initialization escaping construction.

## M1.51 implementation map and test matrix

The implementation map is the one in ADR-0037. The implementation campaign
must add focused declarative and executable coverage for records, enum payloads,
arrays, nested ownership, whole moves, field borrows, replacement, deep clone,
clone-failure cleanup, drop order, CFG joins, loops, parameter and result
transfer, FFI rejection, O0/O1 agreement, native layout, and deterministic
diagnostics. Existing fixed aggregate and dynamic leaf tests remain regression
coverage; they are not evidence that this specification has been implemented.
