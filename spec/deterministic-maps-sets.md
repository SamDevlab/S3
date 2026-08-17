# M1.41 Deterministic Maps and Sets

This is the normative source contract for the closed associative collection
types introduced by M1.41. It extends the M1.39 owned dynamic value contract
and the M1.40 explicit-capacity collection contract.

## 1. Type surface

The only new source types are:

    i64_map
    i64_set

Reference forms are `&i64_map`, `&mut i64_map`, `&i64_set`, and `&mut i64_set`.
Parameterized spellings such as `Map<K,V>` and `Set<T>` are invalid.

## 2. Operations

    i64_map_new(i64) -> i64_map
    i64_map_len(&i64_map) -> i64
    i64_map_capacity(&i64_map) -> i64
    i64_map_reserve(&mut i64_map, i64) -> tryte
    i64_map_put(&mut i64_map, i64, i64) -> tryte
    i64_map_contains(&i64_map, i64) -> trit
    i64_map_get(&i64_map, i64) -> i64
    i64_map_remove(&mut i64_map, i64) -> tryte
    i64_map_key_at(&i64_map, i64) -> i64
    i64_map_value_at(&i64_map, i64) -> i64
    i64_map_clone(&i64_map) -> i64_map

    i64_set_new(i64) -> i64_set
    i64_set_len(&i64_set) -> i64
    i64_set_capacity(&i64_set) -> i64
    i64_set_reserve(&mut i64_set, i64) -> tryte
    i64_set_add(&mut i64_set, i64) -> tryte
    i64_set_contains(&i64_set, i64) -> trit
    i64_set_remove(&mut i64_set, i64) -> tryte
    i64_set_at(&i64_set, i64) -> i64
    i64_set_clone(&i64_set) -> i64_set

Successful mutating status calls return zero tryte. No operation implicitly
grows a collection.

## 3. Ordering and lookup

Map and set traversal order is insertion order. Map replacement keeps the
original position. Removing an element compacts later elements and preserves
their relative order. A duplicate set insertion does nothing. Lookup is
linear and deterministic; hash randomization and pointer identity are not
observable.

## 4. Ownership and borrowing

Maps and sets are move-only owned values. Assignment, by-value parameters, and
by-value returns transfer ownership. After a move, the source is invalid.
Clone creates an independent owned value and preserves the source capacity.
Shared borrows may coexist; a mutable borrow excludes every other borrow.
Owner mutation, reserve, move, and destruction while a conflicting borrow is
active are rejected by the existing semantic/ownership contract.

## 5. Capacity and representation

Length and capacity are non-negative i64 element counts. Capacity arithmetic
must not overflow and the resulting byte allocation must stay within the
M1.39 logical and allocator limits. Map capacity is measured in 16-byte
key/value entries. Set capacity is measured in 8-byte value entries.

The native descriptor and payload address are private implementation details.
Source code cannot inspect descriptors, addresses, element widths, or pointer
arithmetic.

## 6. Checked behavior

Construction and reserve reject negative, overflowing, or over-limit
capacities. Put/add on a full collection traps. Map get, map key/value index,
and set index trap when the requested key/index is absent or out of range.
Map remove and set remove are no-ops for absent values. Contains returns `-1`
for present and `0` for absent.

## 7. IR and native boundary

Typed IR and Assembly carry one logical vector-family collection value while
the closed builtin signature identifies the map or set operation. The native
x86-64 runtime uses the private M1.39 descriptor family and derives entry
offsets from the closed map/set width. No source pointer or descriptor value
is exposed.

## 8. Non-goals

M1.41 does not add generic parameters, arbitrary key/value types, iterators
with independent lifetimes, hash-table semantics, nested owners, concurrent
mutation, or structured result/error values.
