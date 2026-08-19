# M1.82 First-Class Futures, Async Modules, and Generic Async V1

M1.82 adds compiler-owned `Future<T>` syntax on top of M1.81. `Future<T>` is an ownership wrapper: the stable core type checker sees the closed inner `T`, while the async compiler retains separate Future ownership metadata and move analysis.

A Future may be created from an unawaited async call only when the result is stored in a `Future<T>` binding. It may be moved to another Future owner, moved through an async function parameter, or consumed by `await`. Reuse after move/await and overwriting a live Future fail at compile time. Ordinary value use or copying is not permitted. Live unpolled Futures are deterministically dropped with the async frame.

The hosted `MoveOnlyFuture` API remains a runtime contract, but it is no longer the only representation of first-class futures: source-level Future bindings are recognized by the compiler and lowered into executable async IR ownership actions.

Multi-file compilation preprocesses each original source before the existing module compiler rewrites names. Imported async symbols and aliases are mapped to deterministic module-qualified internal identities, and the executable async catalog uses those rewritten identities. An imported async alias can therefore be awaited by the entry module without losing its async classification.

Generic async declarations use the existing closed generic specialization domain (`scalar`, `owned`, `value`). Type arguments remain part of deterministic async action metadata, while the core compiler performs its existing closed specialization/type validation. No unconstrained trait system or runtime type erasure is introduced.

V1 deliberately remains fail-closed: suspension inside general control-flow and ambiguous Future owner shadowing are rejected until the async CFG and lexical Future-id representation can prove those cases. This is preferable to silently reverting to synchronous semantics.
