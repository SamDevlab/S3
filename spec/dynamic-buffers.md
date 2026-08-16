# M1.39 Dynamic Buffers and Text

Status: normative architecture contract for the future M1.39 implementation.

This specification defines the first source-level owned dynamic data values in
S3. It is intentionally smaller than a general collection framework. It does
not introduce generic types, garbage collection, public raw pointers, a
general allocator API, or structured Result propagation.

## 1. Scope and relationship to previous contracts

The current M1.33 contract covers checked half-open ranges for static arrays and
static text. M1.34 covers scalar foreign signatures. M1.35 covers tagged scalar
`DynamicValue` values. Those contracts do not define heap objects, dynamic text,
owned buffers, or an allocator. This document is therefore the first canonical
source contract for those concepts; it does not reinterpret the earlier scalar
contracts.

M1.39 owns only:

- the `bytes` owned octet sequence;
- the `text` owned UTF-8 sequence;
- their move, borrow, allocation, indexing, copying, and deterministic failure
  rules;
- the internal IR and native logical ABI needed to implement those values.

M1.40 owns dynamically sized numeric collections. M1.41 owns maps and sets.
M1.42 owns explicit structured result/error flow. M1.43 owns general host
resource handles and capability enforcement. None of those later milestones
may silently replace the ownership rules in this document.

## 2. Design invariants

1. An owned value has exactly one S3 owner.
2. Assignment, parameter passing, and return transfer ownership; they do not
   copy storage.
3. Deep copy is explicit through `bytes_clone` or `text_clone`.
4. Borrows are non-owning, lexically bounded, and never source pointers.
5. Reallocation is explicit through `*_reserve`; push and append do not grow
   implicitly in M1.39.
6. Allocation addresses and internal owner tokens are not observable.
7. All dynamic lengths and capacities use non-negative `i64` values.
8. `bytes` contains arbitrary octets; `text` always contains valid UTF-8.
9. Operations that can fail in M1.39 use the existing deterministic runtime
   trap channel. M1.39 does not introduce implicit exceptions or a generic
   result type.
10. The compiler never uses the source `&mut` contract as a machine-level
    `noalias` promise. Alias analysis remains conservative.

## 3. Public value model

`bytes` and `text` are ordinary source values with move-only ownership. They
are not explicit integer-like handles, and references to them are not owning
values. The implementation may use a private descriptor and allocation token,
but those are not S3 values and cannot be inspected, compared, serialized, or
converted to integers.

The M1.39 public type surface is exactly:

```text
bytes
text
&bytes
&mut bytes
&text
&mut text
```

There is no `Buffer<T>`, `Vec<T>`, `Bytes<T>`, or `Text<T>` syntax. General
parametric generics remain out of scope. `bytes` is the only dynamic octet
buffer. `text` is the only dynamic text value.

## 4. Ownership and moves

### 4.1 Creation

Creation returns an owned value:

```s3
fn make_bytes() -> bytes:
    return bytes_new(16)

fn make_text() -> text:
    return text_from_static("S3")
```

The capacity argument is an `i64`. It must be non-negative and no greater than
the active buffer limit. The initial length is zero for `bytes_new`. The initial
length for `text_from_static` is the UTF-8 byte length of the literal and its
initial capacity is exactly that length.

### 4.2 Assignment

An owned value is moved by assignment:

```s3
fn move_example() -> bytes:
    first: bytes = bytes_new(4)
    second: bytes = first
    # first is moved and cannot be read, written, borrowed, or returned here.
    return second
```

The source binding becomes unavailable immediately after the move. A use of a
moved binding is a compile-time semantic error. `bytes_clone(&first)` and
`text_clone(&first)` are the only M1.39 deep-copy operations.

### 4.3 Parameters and returns

An owned parameter is consumed by a call. A borrowed parameter is not consumed:

```s3
fn size_of(data: &bytes) -> i64:
    return bytes_len(data)

fn append_mark(data: &mut bytes):
    bytes_push(data, 33)

fn identity(data: bytes) -> bytes:
    return data

fn produce() -> bytes:
    value: bytes = bytes_new(4)
    return value
```

An owned value may be returned from a function. A return transfers ownership
and suppresses the normal local destruction for that value. A borrowed value
may not be returned unless its owner is a parameter whose lifetime is visible
to the caller; M1.39 does not support returning a borrow of a local owner.

### 4.4 Records, arrays, and enums

M1.39 does not allow `bytes` or `text` as fields of records, elements of static
arrays, or payloads of enums. This avoids introducing recursive destruction and
aggregate ownership into the current fixed-layout value model. M1.40 or a later
architecture may lift this restriction without changing the basic move rules.

## 5. Borrow model and aliasing

M1.39 reuses the existing source reference forms `&T` and `&mut T`, but gives
them a specific owner rule for `bytes` and `text`. No lifetime syntax is added.

### 5.1 Borrow creation and end

`&owner` creates a shared borrow and `&mut owner` creates a mutable borrow. A
borrow local is valid until the end of its enclosing lexical block. A temporary
borrow passed directly to a call ends when that call returns. The first
implementation may use this conservative lexical rule; it must not require
last-use or lifetime inference to accept a program.

The owner must outlive every borrow. A borrow cannot be returned from a local
owner, stored in an owned buffer, or copied into a longer-lived record.

### 5.2 Allowed aliases

- Any number of shared `&bytes` or `&text` borrows may coexist.
- A mutable `&mut bytes` or `&mut text` borrow excludes every other borrow of
  the same owner for the borrow interval.
- A move, destruction, `*_reserve`, push, append, or indexed write requires no
  active borrow of the owner.
- The compiler rejects a shared and mutable overlap, multiple mutable borrows,
  mutation while a shared borrow exists, and owner movement while borrowed.
- The backend must not attach a general machine `noalias` attribute solely
  because the source type is `&mut`.

This is a capability rule for dynamic-owner operations, not a global rewrite of
all S3 reference semantics.

### 5.3 Index references

`&bytes[index]`, `&mut bytes[index]`, and references to individual dynamic
octets are out of scope for M1.39. `bytes_get` and `bytes_set` are the only
indexed access forms. This avoids an element reference becoming invalid after
reserve and leaves indexed reference semantics for a later architecture.

## 6. Allocation, capacity, and limits

Allocation is implicit at the explicitly named constructors and copying or
concatenation operations. Users do not select or inject an allocator in M1.39.
The runtime has one target-provided buffer allocator. M1.35 contains no public
allocator contract, so M1.39 does not claim to preserve one.

The logical limits are:

```text
MAX_BUFFER_BYTES = 2147483647
DEFAULT_MAX_BUFFER_BYTES = 67108864
```

The active execution limit is an explicit runtime configuration, analogous to
the existing instruction and frame limits. It may be lower than the logical
maximum but never higher. Capacity arithmetic is checked in `i64`; negative
values, addition overflow, and values beyond the active limit fail before an
allocation request. Host `size_t` behavior is not the language contract.

M1.39 uses exact explicit capacity:

- `bytes_new(n)` allocates capacity `n` and length zero;
- `text_new(n)` allocates capacity `n` and length zero;
- `*_reserve(&mut value, n)` succeeds without changing length and makes
  capacity exactly `n` when `n` is greater than the current capacity;
- reserve with `n < length` fails;
- reserve with `n <= capacity` is a no-op;
- `bytes_push` and `text_append` do not allocate implicitly;
- clone and concat allocate exactly the logical result length;
- a failed allocation leaves the source owner unchanged.

The exact-capacity rule is deliberately less convenient than an automatic
growth factor. It makes capacity and allocation behavior deterministic and
leaves growth policy for M1.40 collections.

## 7. Bytes operations

The M1.39 byte API is a closed built-in family, not a generic library:

```text
bytes_new(capacity: i64) -> bytes
bytes_len(value: &bytes) -> i64
bytes_capacity(value: &bytes) -> i64
bytes_get(value: &bytes, index: i64) -> tryte
bytes_set(value: &mut bytes, index: i64, octet: tryte)
bytes_push(value: &mut bytes, octet: tryte)
bytes_reserve(value: &mut bytes, capacity: i64)
bytes_clone(value: &bytes) -> bytes
bytes_concat(left: &bytes, right: &bytes) -> bytes
bytes_slice(value: &bytes, start: i64, end: i64) -> bytes
bytes_from_text(value: &text) -> bytes
text_from_bytes(value: &bytes) -> text
```

The logical octet domain is `0..255`, represented at the source boundary by a
`tryte`. `bytes_get` returns a `tryte` in that restricted domain. A set or push
with a value outside `0..255` traps with `S3E_BUFFER_OCTET_RANGE`.

All indices use non-negative `i64` values and the existing half-open rule. An
index `i` is valid exactly when `0 <= i < length`. `bytes_slice` returns a new
owned copy and never returns a view.

## 8. Text model

`text` stores valid UTF-8 bytes, has no NUL terminator, and has no pointer or
address identity. `text_len` returns byte length, not code-point or grapheme
count. M1.39 provides no direct text indexing. A slice must begin and end at
UTF-8 code-point boundaries; an interior boundary traps with
`S3E_TEXT_BOUNDARY`.

The text API is:

```text
text_new(capacity: i64) -> text
text_from_static(value: string) -> text
text_len(value: &text) -> i64
text_capacity(value: &text) -> i64
text_reserve(value: &mut text, capacity: i64)
text_append(value: &mut text, suffix: &text)
text_append_static(value: &mut text, suffix: string)
text_clone(value: &text) -> text
text_concat(left: &text, right: &text) -> text
text_slice(value: &text, start: i64, end: i64) -> text
text_find(value: &text, needle: &text) -> i64
text_from_bytes(value: &bytes) -> text
bytes_from_text(value: &text) -> bytes
```

Static string literals are validated by the existing source lexer. Conversion
from arbitrary bytes validates the full range before creating the destination;
invalid UTF-8 traps with `S3E_TEXT_INVALID_UTF8`. `text_append` and
`text_append_static` require enough reserved capacity. This milestone does not
define grapheme operations, locale, normalization, case mapping, float
formatting, or code-point indexing.

## 9. Error boundary

M1.39 does not return a generic structured result. The following are compile-
time errors:

- use after move: `S3E_SEMANTIC_USE_AFTER_MOVE`;
- borrow escaping an owner: `S3E_SEMANTIC_BORROW_ESCAPE`;
- overlapping shared/mutable or mutable/mutable borrows:
  `S3E_SEMANTIC_BORROW_CONFLICT`;
- owner move, destruction, or reserve while borrowed:
  `S3E_SEMANTIC_BORROWED_OWNER`;
- unsupported dynamic value nesting or type: `S3E_SEMANTIC_DYNAMIC_TYPE`.

The following are deterministic runtime traps and never produce a partially
initialized owner:

- invalid index: `S3E_BUFFER_BOUNDS`;
- octet outside `0..255`: `S3E_BUFFER_OCTET_RANGE`;
- negative/overflow/excess capacity: `S3E_BUFFER_CAPACITY`;
- allocator rejection: `S3E_BUFFER_ALLOCATION`;
- push/append without capacity: `S3E_BUFFER_FULL`;
- invalid UTF-8: `S3E_TEXT_INVALID_UTF8`;
- non-boundary text slice: `S3E_TEXT_BOUNDARY`.

M1.42 may provide explicit result wrappers for these failures, but it must not
change the ownership or leave the M1.39 trap path ambiguous.

## 10. Logical IR and SSA model

An owned buffer is one logical typed IR value. It is not scalarized into three
independent source values. The semantic IR carries a private `BufferKind`
(`BYTES` or `TEXT`) and an ownership state. The first implementation may use
the following semantic operation family; names are versioned internal IR names
and are not source opcodes:

```text
BUFFER_ALLOC(kind, capacity) -> owned_buffer
BUFFER_DROP(owned_buffer)
BUFFER_LEN(borrowed_buffer) -> i64
BUFFER_CAPACITY(borrowed_buffer) -> i64
BUFFER_LOAD(borrowed_buffer, index) -> tryte
BUFFER_STORE(mutable_borrowed_buffer, index, tryte)
BUFFER_PUSH(mutable_borrowed_buffer, tryte)
BUFFER_RESERVE(mutable_borrowed_buffer, capacity)
BUFFER_CLONE(borrowed_buffer) -> owned_buffer
BUFFER_SLICE_COPY(borrowed_buffer, start, end) -> owned_buffer
BUFFER_CONCAT(borrowed_left, borrowed_right) -> owned_buffer
BUFFER_UTF8_VALIDATE(bytes) -> text_or_trap
BUFFER_DROP(owned_buffer)
```

Text-specific append/find/format operations may lower to this family plus
checked helper operations. The public IR schema must version the new value and
operation families together; an implementation must not encode a Python object
or an untyped host pointer into public IR JSON.

Owned values are linear through SSA:

- a move consumes the source SSA owner and produces one destination owner;
- a clone produces a distinct owner;
- `BUFFER_DROP` consumes exactly one owner;
- a CFG join requires the same ownership availability on every predecessor;
- a moved owner on one predecessor and available owner on another is rejected;
- a loop backedge must return the same owner state as its loop header;
- a return consumes the returned owner and drops all other live locals;
- branch exits drop owners that do not leave the branch.

The compiler may conservatively reject a program whose ownership state cannot be
proven. It must not duplicate or silently leak an owner to make a join pass.

## 11. Runtime layout

The normative logical descriptor is:

```text
owned buffer = { private storage identity, length: i64, capacity: i64, kind }
```

Storage identity is not observable. A native backend may represent it as
`{base_address, length, capacity}` plus private allocator metadata. The base
address and allocator token are not source values, are not serialized, and are
not compared for equality. Empty values may use a null private base with zero
length and capacity.

The hosted emulator must implement the same logical operations and failure
ordering without exposing Python object identity. Allocation order must not
affect program-visible results.

## 12. Native ABI and FFI

Within S3, an owned value crosses a function boundary by ownership transfer in
descriptor order `(private base, length, capacity)`. The existing aggregate
return/sret mechanism may carry this descriptor; the backend chooses the
register/stack placement under the existing private S3 ABI. The logical order,
move, and drop obligations are fixed.

`&bytes` and `&text` at a C boundary are borrowed views represented as exactly:

```text
(base_address: private pointer, length: i64)
```

This preserves the M1.34-style base/length view direction. The C callee may read
the bytes during the call but may not retain the address, mutate through a
shared view, free it, or assume NUL termination. `&mut bytes` and `&mut text`
are not exposed to C in M1.39. S3 ownership never crosses FFI. Any foreign
violation is the caller's contract violation; the compiler cannot make foreign
code safe by adding a hidden owner.

## 13. Destruction

The compiler inserts `BUFFER_DROP` at lexical scope exits for every live owner.
Moves remove the source drop obligation. Returns transfer the obligation to the
caller. Branches, loop exits, `break`, and `continue` use the SSA ownership
rules above. There is no source `free`, reference counting, finalizer, or GC.

If a runtime trap terminates the current hosted/native execution, ordinary
process termination reclaims physical memory; no user-visible destructor order
is promised after the trap. Before a successful call or normal control-flow
exit, all compiler-inserted drops are deterministic.

## 14. Cross-module policy

Owned `bytes` and `text` are valid in exported and imported S3 function
parameters and returns. The imported function consumes or borrows according to
the declared type. They are not valid in records, static arrays, or enum
payloads in M1.39. S3 module ABI is distinct from the C FFI ABI.

## 15. Negative contract

| Case | Required result |
| --- | --- |
| use after move | compile-time `S3E_SEMANTIC_USE_AFTER_MOVE` |
| borrow escapes local owner | compile-time `S3E_SEMANTIC_BORROW_ESCAPE` |
| shared and mutable overlap | compile-time `S3E_SEMANTIC_BORROW_CONFLICT` |
| reserve/push while borrowed | compile-time `S3E_SEMANTIC_BORROWED_OWNER` |
| index outside `[0, length)` | runtime `S3E_BUFFER_BOUNDS` |
| capacity negative, overflowing, or over active limit | runtime `S3E_BUFFER_CAPACITY` |
| allocator rejects request | runtime `S3E_BUFFER_ALLOCATION` |
| push/append with insufficient capacity | runtime `S3E_BUFFER_FULL` |
| invalid UTF-8 conversion | runtime `S3E_TEXT_INVALID_UTF8` |
| text slice at interior byte | runtime `S3E_TEXT_BOUNDARY` |
| dynamic buffer nested in record/array/enum | compile-time `S3E_SEMANTIC_DYNAMIC_TYPE` |
| generic `Buffer<T>` or `Vec<T>` syntax | compile-time unsupported-type diagnostic |
| public raw pointer or pointer arithmetic | compile-time unsupported-type diagnostic |

There is no undefined-behavior category in the S3 source contract for these
operations.

## 16. Explicit non-goals

M1.39 does not define numeric vectors, maps, sets, generic syntax, records with
owned fields, element references, automatic growth, a user allocator, a public
pointer type, GC, exceptions, async, threads, C ownership transfer, NUL
termination, code-point indexing, grapheme semantics, locale, or structured
result propagation.
