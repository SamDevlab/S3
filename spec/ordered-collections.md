# M1.40 Ordered Collections

This is the normative source contract for the closed ordered vector types
introduced by M1.40. It extends the M1.39 owned dynamic value contract and
does not introduce a generic type system.

## 1. Type surface

The only new source types are:

    tryte_vector
    i64_vector
    f64_vector

Reference forms are &tryte_vector, &mut tryte_vector, and the equivalent forms
for the other two vector types. Vector<T>, Buffer<T>, and all other
parameterized spellings are invalid. GENERAL_PARAMETRIC_GENERICS=NO.

## 2. Operations

Each family substitutes its prefix in this table:

    <prefix>_vector_new(i64) -> <prefix>_vector
    <prefix>_vector_len(&<prefix>_vector) -> i64
    <prefix>_vector_capacity(&<prefix>_vector) -> i64
    <prefix>_vector_reserve(&mut <prefix>_vector, i64) -> tryte
    <prefix>_vector_push(&mut <prefix>_vector, element) -> tryte
    <prefix>_vector_pop(&mut <prefix>_vector) -> element
    <prefix>_vector_get(&<prefix>_vector, i64) -> element
    <prefix>_vector_set(&mut <prefix>_vector, i64, element) -> tryte
    <prefix>_vector_clone(&<prefix>_vector) -> <prefix>_vector
    <prefix>_vector_slice(&<prefix>_vector, i64, i64) -> <prefix>_vector

The prefixes and elements are tryte, i64, and f64 respectively. Successful
mutating status calls return the zero tryte. No status call implicitly grows
a vector.

## 3. Ownership and borrowing

Vectors are ordinary move-only owned values. Construction, clone, and reserve
may allocate through the M1.39 allocator. Assignment, by-value parameters, and
by-value returns transfer ownership. After a move, the source is invalid and
any use, including &source, is a semantic use-after-move diagnostic. Clone is
a deep copy and preserves the source capacity. Slice is a new owned copy with
capacity equal to its length.

Shared borrows may coexist. One mutable borrow excludes every other borrow.
While a borrow is active, move, reserve, push, pop, set, and scope destruction
of the owner are rejected. A vector operation never returns a view whose
lifetime outlives its owner.

## 4. Capacity and element representation

Length and capacity are non-negative i64 element counts. Capacity arithmetic
must not overflow and the resulting byte allocation must be no greater than
the M1.39 logical maximum of 2147483647 bytes and the active allocator limit.
The default active limit remains 67108864 bytes.

tryte_vector stores signed trytes in a two-byte native layout. i64_vector and
f64_vector store one eight-byte payload per element. These are backend
representation constraints, not source-visible byte arrays. Vector ordering is
declaration/operation order and is independent of allocation addresses.

## 5. Checked operations

get, set, pop, and slice use checked indices and half-open bounds. push and
reserve trap on full capacity, negative capacity, byte-limit overflow, or
allocation failure. A tryte element outside [-364, 364] is a deterministic
range trap. i64 and f64 values use their existing scalar validation rules.
There is no wraparound.

## 6. Determinism and iteration

Vectors preserve insertion order. The supported deterministic traversal is an
index sequence from zero through len - 1; no hash ordering or pointer identity
is observable. Mutation during a borrow is rejected, so a traversal that
holds a shared borrow observes a stable sequence. M1.40 does not add a
separate public iterator object.

## 7. IR and native boundary

In typed IR and Assembly, a vector is one logical vector value. Calls carry the
closed element signature, while the physical value uses the private M1.39
descriptor family. The native x86-64 runtime stores a private
(base, byte_length, byte_capacity) descriptor and uses the operation family to
apply the element width. No source pointer, descriptor comparison, or pointer
arithmetic is exposed.

The C/FFI policy remains M1.39's borrowed (base, i64 length) view policy;
ownership transfer is deferred to the later interop milestone.

## 8. Non-goals and future boundary

M1.40 does not add records/enums/nested vectors as elements, deques, maps,
sets, concurrent mutation, implicit sharing, generic parameters, structured
error values, or a new allocator API. M1.41 owns deterministic maps/sets and
M1.42 owns explicit result/error flow.
