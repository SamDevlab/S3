# M1.64 Architecture Preflight

## Existing authority

ADR-0030 defines nominal payload enums, exhaustive `match`, explicit error
variants, and the existing multi-cell aggregate ABI as the single result
representation. It explicitly rejects exceptions, unwinding, a generic
`Result<T,E>` compiler primitive, and hidden `?` propagation.

Parametric enums from M1.54 already provide the compiler-known equivalent of
`Result[T,E]` and `Option[T]` for closed scalar/value arguments. The semantic,
lowering, IR, Assembly, and hosted execution paths are already able to carry
and match those fixed layouts.

## Selected implementation

Add a small immutable hosted `Result[T, E]`/`Option[T]` API for host-side
contracts and tests. Use `fold`, `map`, and `bind` as explicit operations;
errors remain values. Add no parser token or implicit propagation path. Prove
the source-level generic form with explicit exhaustive matches and O0/O1
execution.

## Rejected alternatives

- A new `?` token would contradict ADR-0030 and create hidden control flow.
- Exceptions or unwinding would violate deterministic ownership cleanup.
- A second compiler aggregate layout would violate the existing ABI contract.

## Environment

Native execution is subject to the existing local toolchain availability and
will be recorded as a deferment rather than represented as a false pass.
