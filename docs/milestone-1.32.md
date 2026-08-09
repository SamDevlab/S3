# Milestone 1.32 - Bounded Heap Foundation

Milestone 1.32 introduces the bounded heap provider used by later lifetime
work. It gives allocations explicit logical identities and deterministic
storage limits without exposing host addresses.

## Contract

- `BoundedHeap` is bounded by allocation count and total element count.
- `HeapHandle` contains a heap identity, allocation identity, and fixed length.
- Allocation IDs are deterministic within one heap instance.
- Reads and writes validate heap identity and element bounds.
- `snapshot()` is ordered by allocation identity and is suitable for
  differential comparison.
- `close()` ends the heap lifetime; handles cannot be reused afterward.
- There is no free, garbage collection, reference return, raw pointer,
  nullable reference, or implicit lifetime extension in this milestone.

Existing frame-backed `.memory` and V1 stack-reference semantics remain
unchanged. Integration with escape analysis and safe reference returns belongs
to Milestone 1.33.

## Validation

The focused contract lives in `tests/test_heap.py` and covers identity,
storage, deterministic limits, foreign handles, bounds, and closure.
