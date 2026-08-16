# Milestone 1.40 - Deterministic Ordered User Collections

Status: COMPLETE.

## Goal

Provide bounded, ordered, growable numeric collections without introducing
general generics or a second ownership system.

## Normative contract

- ADR-0028 deterministic ordered collections
- spec/ordered-collections.md
- spec/dynamic-buffers.md

## Public types and operations

M1.40 adds the closed types tryte_vector, i64_vector, and f64_vector. Each
family provides new, len, capacity, reserve, push, pop, get, set, clone, and
slice through its type-specific built-ins. Capacity is an exact element count;
push does not grow implicitly.

## Implementation

The hosted runtime uses DynamicVector with the M1.39 allocator, move, borrow,
limit, and deterministic trap rules. The compiler preserves a logical vector
value through IR and Assembly. Linux x86-64 uses the private descriptor family
with two-byte tryte elements and eight-byte i64/f64 elements. No public generic
syntax or pointer value is added.

## Acceptance gates

- focused hosted vector operations and negative semantic diagnostics;
- compileall and IR/Assembly verifier regression;
- O0/O1 hosted equivalence;
- Linux x86-64 native create/reserve/push/pop/index/clone/slice probes;
- fixed-seed differential traces against a Python reference sequence;
- one terminal full suite after focused gates;
- git diff --check and no benchmark special case.

## Non-goals

Maps/sets, structured results, records or nested owners as elements, public
iterators with independent lifetimes, concurrent mutation, and general
parametric generics remain deferred.

## M1.41 boundary

M1.40 focused, native, differential, and full-suite gates are terminal and
green. M1.41 owns deterministic maps and sets; it must not reopen vector
ownership or capacity semantics.
