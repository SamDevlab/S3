# M1.69 Architecture Preflight

## Existing authority

The existing runtime uses multiprocessing only inside the test runner and has
no source-level thread or shared-state primitive. M1.64 already defines
explicit Result values for recoverable failures.

## Selected implementation

Use native Python `threading.Thread` behind an explicit `ThreadRuntime`.
Ownership transfer is represented by `OwnedValue.move()`, while immutable
scalars/tuples are accepted as copyable inputs. Handles are non-daemon and
must be joined; the runtime has a maximum active-thread bound. Worker failures
are converted to typed values at the boundary.

## Boundary

No detached lifecycle, implicit sharing, borrow escape, exception propagation,
or refcount/GC ownership model is introduced. Full compiler static move/borrow
diagnostics remain governed by the existing semantic ownership rules.
