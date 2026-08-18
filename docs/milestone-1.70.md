# Milestone 1.70 - Atomics and Synchronization V1

## Architecture status

M1.70 adds a bounded hosted synchronization provider in
`bootstrap.s3.synchronization`. `AtomicI64` exposes checked load, store,
fetch-add, and compare-exchange operations with the five declared memory
orders. Invalid operation/order pairs, i64 values, and overflow are explicit
`Result` errors. The implementation is deliberately lock-backed and makes no
lock-free claim.

`Mutex[T]` owns one protected value. Access is available only through a
`MutexGuard`; the guard supports bounded get/set operations, context-manager
use, and idempotent deterministic release. A timeout is an explicit error and
there is no raw operating-system mutex handle in the public surface.

## Safety boundary

This milestone does not introduce general reference counting, GC, detached
threads, condition variables, async scheduling, raw pointers, or an arbitrary
shared-mutation proof system. Callers must make sharing explicit by passing a
`Mutex` or `AtomicI64` to an already-owned thread entry. The provider does not
claim static race freedom for arbitrary Python or future S3 code.

## Tests and environment

Focused tests cover atomic operations, memory-order validation,
compare-exchange, overflow preservation, guard lifecycle, timeout behavior,
context-manager cleanup, and a bounded four-thread counter. Hosted T0/T1/T2/T3
gates are required. Native Windows/Linux execution certification remains an
environment gate for this isolated Windows campaign.
