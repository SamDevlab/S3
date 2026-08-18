# M1.70 Architecture Preflight

## Existing contracts

- `bootstrap/s3/threads.py` provides explicit non-detached thread ownership and
  join results from M1.69.
- `bootstrap/s3/results.py` provides the repository's explicit hosted result
  value for recoverable errors.
- `bootstrap/s3/numeric.py` defines the canonical checked i64 domain.
- `bootstrap/s3/memory_effects.py` describes reference-visible IR effects but
  does not expose a synchronization primitive.

## Selected boundary

M1.70 adds `AtomicI64`, `Mutex[T]`, and `MutexGuard[T]` in a new provider
module. Atomics use a private host lock and explicitly report
`lock_free = False`; this is a correctness-first provider contract, not a
native lock-free guarantee. The memory-order set is closed to relaxed,
acquire, release, acq_rel, and seq_cst. Load/store and compare-exchange order
rules are validated before state access.

Mutex access is guard-scoped and deterministic. The provider returns typed
`Result` errors for invalid timeout, closed guard, timeout, invalid i64, and
overflow cases. Condition variables, Once, general shared ownership, GC,
raw-pointer APIs, async, and static race proofs remain out of scope.

## Certification boundary

The hosted provider and bounded multi-thread test are testable on this host.
Linux native and Windows native execution are not claimed by this local
campaign because the required external native certification environments are
not part of the isolated worktree gate.
