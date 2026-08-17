# Milestone 1.41 - Deterministic Maps and Sets

Status: COMPLETE.

## Goal

Add closed, ordered `i64_map` and `i64_set` values with explicit capacity,
move/borrow safety, hosted/emulated behavior, and Linux x86-64 native support.

## Contract

- ADR-0029 deterministic maps and sets
- spec/deterministic-maps-sets.md
- M1.39 dynamic buffer ownership and allocator rules
- M1.40 explicit-capacity ordered collection rules

Maps store i64 key/value pairs. Sets store i64 values. Both preserve insertion
order and use deterministic linear lookup. No public generic type syntax,
implicit growth, address observation, or hash randomization is introduced.

## Implementation

The hosted runtime implements `DynamicMap` and `DynamicSet` on the established
allocator and borrow model. The IR emulator dispatches the closed builtin
families. Lowering, IR signatures, parser/semantic types, and Assembly
verification preserve the logical collection type while using the private
collection descriptor family. Linux x86-64 implements 16-byte map entries and
8-byte set entries.

## Verification gates

- focused M1.41 map/set tests: PASS (7 tests);
- shared M1.39/M1.40/M1.41 regression group: PASS (40 tests);
- compileall: PASS;
- git diff --check: PASS;
- Linux x86-64 native probes: PASS for lookup, replacement, order,
  compaction, deduplication, reserve, and clone;
- full suite on implementation HEAD: terminal exit 0;
- no benchmark special case and no remote write.

## Boundary

M1.41 is closed. M1.42 is the next milestone and must not reopen the map/set
ownership or capacity contract. General collections, structured result/error
values, and richer key domains remain deferred.
