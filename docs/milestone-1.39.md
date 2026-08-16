# Milestone 1.39 - Owned Dynamic Buffers and UTF-8 Text

Status: architecture closed; implementation not started.

## Goal

Add the first source-level runtime data values that can own and process dynamic
octets and UTF-8 text while preserving S3's deterministic, bounded, explicit
systems-language identity.

## Problem and dependencies

Static arrays and static string handles cannot process runtime input, construct
diagnostics, or support ordinary file and tool workloads. M1.39 depends on the
existing checked index/range, mutability, reference, IR, hosted execution, and
Linux x86-64 native contracts. The earlier M1.33-M1.35 documents do not provide
a heap or allocator; this milestone defines the missing contract.

Normative references:

- [ADR-0027](decisions/ADR-0027-m1.39-owned-dynamic-buffer-contract.md)
- [Dynamic buffers specification](../spec/dynamic-buffers.md)
- [M1.39 architecture closure report](../reports/m1.39-architecture/M139_DYNAMIC_BUFFER_ARCHITECTURE_CLOSURE.md)

## Public types

Exactly `bytes`, `text`, `&bytes`, `&mut bytes`, `&text`, and `&mut text` are
introduced. `bytes` is arbitrary octets. `text` is valid UTF-8. There is no
`Buffer<T>`, `Vec<T>`, generic-looking type constructor, public pointer, or
owned dynamic value nested in a record, static array, or enum.

## Public operation surface

```text
bytes_new(i64) -> bytes
bytes_len(&bytes) -> i64
bytes_capacity(&bytes) -> i64
bytes_get(&bytes, i64) -> tryte
bytes_set(&mut bytes, i64, tryte)
bytes_push(&mut bytes, tryte)
bytes_reserve(&mut bytes, i64)
bytes_clone(&bytes) -> bytes
bytes_concat(&bytes, &bytes) -> bytes
bytes_slice(&bytes, i64, i64) -> bytes
bytes_from_text(&text) -> bytes
text_from_bytes(&bytes) -> text

text_new(i64) -> text
text_from_static(string) -> text
text_len(&text) -> i64
text_capacity(&text) -> i64
text_reserve(&mut text, i64)
text_append(&mut text, &text)
text_append_static(&mut text, string)
text_clone(&text) -> text
text_concat(&text, &text) -> text
text_slice(&text, i64, i64) -> text
text_find(&text, &text) -> i64
```

The concrete examples and all failure conditions are in the normative spec.

## Ownership and allocation

Owned values move on assignment, parameter passing, and return. Deep copies are
explicit. Borrows are lexical and non-owning; shared borrows may coexist, one
mutable borrow excludes all other borrows, and no owner may move, drop, reserve,
push, append, or return while borrowed. The compiler inserts deterministic drop
operations at scope exits.

M1.39 uses a target-provided allocator with explicit capacity. `reserve` is
exact and push/append do not grow implicitly. The logical maximum is
`2147483647` bytes and the default active limit is `67108864` bytes. Addresses
and allocation tokens are not observable.

## Text and failure semantics

Text length is measured in UTF-8 bytes. M1.39 has no direct code-point indexing
or grapheme semantics. Slices must use code-point boundaries. Compile-time
ownership/borrow violations are diagnostics. Bounds, capacity, allocation,
invalid octet, invalid UTF-8, and invalid text boundary failures are
deterministic runtime traps; M1.42 may later expose structured result wrappers.

## Implementation boundary

M1.39 owns bytes/text and their internal logical IR. M1.40 owns numeric ordered
collections and growth policy. M1.41 owns maps/sets. M1.42 owns structured
error propagation. M1.43 owns general resource handles/capabilities. M1.39
must not absorb any of those later features.

## Acceptance gates

The executable gate IDs are defined in the architecture closure report. The
implementation campaign must map every gate to hosted, O0/O1, native,
differential, determinism, ownership, allocation-failure, cross-module, and
borrow-negative evidence as applicable. This document does not add executable
tests.

## Non-goals

No general generics, GC, public raw pointers, automatic buffer growth, numeric
vectors, maps, records containing owners, element references, exceptions,
structured Result values, threads, async, or C ownership transfer.
