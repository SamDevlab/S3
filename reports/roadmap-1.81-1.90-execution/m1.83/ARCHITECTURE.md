# M1.83 Architecture

M1.83 provides a fixed-worker bounded executor for move-only Futures. Task admission is one lock transaction: closed/capacity checks, Future ownership move, task-id reservation, task insertion, and initial ready-queue admission cannot be interleaved by a competing submitter.

The executor tracks queued and actively-polled task ids separately. A wake that arrives while a task is actively being polled is recorded as one deferred wake rather than enqueuing a second copy. A worker leaves the active set before a deferred follow-up poll can be admitted, enforcing the exactly-one-active-poll invariant. Wakeups remain deduplicated and ready-queue capacity is bounded.

Cross-thread transfer uses the closed immutable `TransferValue` domain: scalars, text/bytes, and recursively transfer-safe tuples. Mutable containers and arbitrary host objects fail closed. Submission consumes Future ownership. Terminal tasks are removed, shutdown cancels unfinished owners, signals and joins all workers, and clears bounded executor state.

Concurrency correctness tests use barriers/events for atomic admission and active-poll races; they do not depend on random sleeps to create the race. Runtime completion order across workers is not promised deterministic, while task ownership and result semantics are.
