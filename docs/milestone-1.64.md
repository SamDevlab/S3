# Milestone 1.64 - Explicit Result Propagation V1

## Architecture status

M1.64 closes bounded explicit result/error vocabulary for the hosted runtime
and generic source enums. `Result[T, E]` and `Option[T]` are represented by
closed immutable `Result` and `Option` values in `bootstrap.s3.results`, with
explicit `fold`, `map`, `bind`, and defaulting operations. The source-language
equivalent remains a parametric nominal enum inspected by exhaustive `match`.

Propagation is explicit control flow. A caller matches the result and returns
the selected success or error variant; this is the canonical S3 form and is
the same representation used by the existing IR and aggregate-return ABI.

## Safety boundary

No exceptions, stack unwinding, hidden allocation, sentinel status values, or
implicit `?` operator were added. `bind` is an explicit hosted combinator and
does not convert an error into an exception or hide ownership transitions.
The compiler continues to reject using an aggregate result as a scalar without
matching it first, and source enums retain fixed deterministic layouts.

## Public surface and tests

The hosted surface is `bootstrap.s3.results.Result` and
`bootstrap.s3.results.Option`. Tests cover success/error, present/absent,
explicit composition, generic source enums, O0/O1 equivalence, and callback
contract validation. Existing aggregate-result, enum, IR, and native tests
remain the subsystem and cross-subsystem gates.

## Out of scope

Exceptions, unwinding, unchecked unwrap, hidden propagation syntax, general
traits, and a second aggregate representation remain out of scope. Native
certification is reported separately when the local toolchain is unavailable.

## Dependency

M1.65 may use the same explicit enum/result ABI for target-specific lowering.

## Implementation status and environment

COMPLETE for explicit hosted values and source-level exhaustive matching.
Linux native certification is `DEFERRED_BY_ENVIRONMENT`; no hidden propagation
operator was introduced because ADR-0030 requires explicit control flow.
