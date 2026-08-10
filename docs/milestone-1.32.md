# Milestone 1.32 - Numeric Domains And Large Indexing

This milestone introduces the programmer-visible numeric foundation for large
scalar and index domains.

## Required capability

- signed `i64` scalar values;
- finite IEEE-754 `f64` scalar values;
- checked large non-negative indices and lengths;
- numeric IR and emulator semantics;
- native `i64` lowering;
- native `f64` lowering through SSE2 and the internal System V AMD64 float ABI.

The existing tryte language and Assembly 0.6 path remain compatible while this
capability is integrated incrementally. Numeric values are never silently
coerced between `i64` and `f64`; mixed-domain arithmetic is rejected.

## Current implementation boundary

The canonical domains, typed numeric IR evaluator, large-index model, public
IR/Assembly type names, ABI register contract, initial native lowering contract
(`addq`, `addsd`, `movq`, and `movsd`), numeric `ADD` execution in the main
IR verifier/emulator, and the constant/return path through lexer, parser,
semantic analysis, and lowering are implemented. Complete verifier activation,
complete native instruction emission, and end-to-end differential coverage
remain milestone work.

The superseded heap-first implementation is intentionally excluded from this
milestone and remains preserved on its original branch for possible M1.35 use.
