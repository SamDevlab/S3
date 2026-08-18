# Milestone 1.69 - Threads V1

## Architecture status

M1.69 adds a bounded explicit transfer model in `bootstrap.s3.threads`.
`OwnedValue.move()` consumes a value before the thread starts; scalar and
immutable tuple values can be passed directly. A `ThreadHandle` is non-daemon,
owns the running thread, and returns the worker result or a typed `ThreadError`
through `join()`.

Join is explicit and exactly once. A timeout is a single terminal observation,
not a hidden retry. `close()` refuses to discard a running thread, and
`join_all()` provides a bounded owner operation. Worker exceptions are caught at
the provider boundary and mapped to `WORKER_FAILURE`; they are not propagated
as cross-thread unwinding. Direct arguments are limited to immutable values or
explicit synchronization roots; arbitrary mutable objects must be wrapped in
`OwnedValue` before transfer.

## Safety boundary

No detached threads, unrestricted shared mutable state, GC finalizer cleanup,
raw thread handles, or general shared ownership were added. Static borrow
escape diagnostics remain a compiler-language follow-up; this provider accepts
only explicit owned wrappers, copyable immutable values, or explicit
synchronization roots. Arbitrary direct mutable sharing is rejected.

## Implementation status, environment, and dependency

COMPLETE for the bounded hosted thread provider. Windows native execution is
`DEFERRED_BY_ENVIRONMENT`; M1.70 consumes the explicit synchronization-root
boundary and adds shared-state primitives.
