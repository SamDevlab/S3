# M1.83 Architecture

M1.83 adds a bounded multithread executor around the move-only Future from
M1.82. The executor has a fixed worker count, a bounded ready queue, bounded
task admission, deterministic task identifiers, and explicit wakeups. A
pending task is not re-polled implicitly; its owner or an I/O provider must
explicitly wake it.

Cross-thread transfer uses a closed `TransferValue` domain. Scalar values,
text, bytes, and recursively closed tuples are accepted; mutable containers,
arbitrary host objects, and implicit aliases are rejected. Submission consumes
the Future owner and the transfer token. Workers publish only immutable poll
records under a lock, and `close()` cancels unfinished work, signals every
worker, joins them, and clears the queue.

This is a hosted implementation of the ownership and boundedness contract.
The language remains free of shared mutable values, raw pointers, GC, and
exception-driven control flow. Native execution certification is deferred when
the required target environment is unavailable.
