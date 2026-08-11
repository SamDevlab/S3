# Milestone 1.35 - Dynamic Owned Data

M1.35 extends the scalar dynamic boundary with runtime-owned contiguous data.
`Allocator` is an injectable provider with deterministic allocation limits.
`OwnedBuffer[int]` and `OwnedBuffer[float]` provide runtime `len`, `capacity`,
checked indexing, `push`, and geometric growth. `DynamicBytes` and
`DynamicText` use the same owned storage contract.

`BorrowedSlice` is a bounded view over the owned storage. It retains the
owner, exposes the base address and runtime length for the M1.34 FFI boundary,
and permits mutation only when explicitly borrowed as mutable. Growing a
buffer reallocates and copies the existing elements exactly once; borrowing
does not copy. Allocation failures are deterministic and use-after-free is
prevented by the retained owner reference.

The Linux E2E proof passes an `OwnedBuffer[int]` directly to exported S3
`&[i64]` and `&mut [i64]` functions and verifies host-visible mutation.
Dynamic strings remain UTF-8 byte storage; unbounded heap policy and GC are
outside this milestone.
