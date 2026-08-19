# M1.82 Architecture

M1.82 makes the resumable result of an async function a first-class,
move-only Future. The Future is an explicit owner of one `AsyncFuture` poll
machine: it can be stored, returned, moved to another owner, and polled by
one consumer. Copying or concurrent polling is rejected. Terminal ownership
is consumed exactly once and cancellation drops the underlying frame through
the existing deterministic frame cleanup path.

Async functions are described by a stable module-qualified identity. A
registry owns declarations and rejects duplicate module/function identities.
Generic async declarations are specialized only from a closed, constrained
type domain. The specialization key includes the module, function, and every
type argument, so two modules cannot accidentally share a Future identity.

The implementation is hosted and provider-neutral. It does not introduce
generators, implicit cloning, shared mutable state, raw pointers, a garbage
collector, or an exception-based language control path. Poll budgets and
generic argument counts are bounded and invalid inputs fail closed.

The native async IR from M1.81 remains the execution authority; this layer
only gives that execution a first-class ownership and module/generic contract.
Native ARM execution certification remains environment-dependent.
