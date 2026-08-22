# M1.92 Architecture: Synchronization Primitives

M1.92 adds `BoundedMutex` and `BoundedEvent` to the hosted async substrate.
Both primitives use explicit non-generator state and bounded FIFO waiter
queues. Mutex ownership is represented by a `MutexGuard`; releasing a guard
promotes exactly one waiter and emits one wakeup. Manual events wake all
registered waiters in registration order; auto-reset events wake one waiter.

Waiter registration, cancellation, duplicate wait, double unlock, and queue
overflow are explicit `Result` errors. Queue capacity is reserved by the
waiter bound, so a successful registration cannot later lose its wakeup due to
an unbounded or overfull queue.
