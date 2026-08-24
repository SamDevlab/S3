# Milestone 2.73: Bounded Self-Hosted Scalar Type Checking Candidate

M2.73 adds a bounded S3-authored scalar type-checking contract to the semantic
self-hosting train.

## Scope

The candidate checks exact scalar assignment compatibility, arithmetic,
comparisons and the explicit numeric conversions used by the compiler subset.
The scalar domains are `trit`, `tryte`, `i64` and `f64`, represented by stable
numeric type IDs. Arithmetic preserves the common operand type; comparisons
produce `trit`; and conversion acceptance mirrors the existing semantic
contract for `to_i64`, `to_f64` and `to_tryte`.

The candidate returns a canonical accepted-result type or a canonical rejection
code. The Python adapter validates the bounded request and compares the S3
result with an independent reference rule set. It does not inject the answer
into the S3 execution.

## Evidence Contract

- S3 source: `selfhost/semantic/scalar_type_checking_candidate.s3`.
- Python adapter/reference: `bootstrap/s3/scalar_type_checking_candidate.py`.
- Focused contract: `tests/test_m273_scalar_type_checking.py`.
- Scalar type IDs: `trit=1`, `tryte=2`, `i64=3`, `f64=4`.
- Assignment requires exact scalar type equality.
- `*` and `/` require `i64` or `f64` operands.
- Balanced-ternary minimum/maximum require `trit` or `tryte` operands.
- Comparisons require matching scalar domains and return `trit`.
- Explicit conversion rules are fail-closed and deterministic.
- Python remains the reference/default compiler path.

## Non-claims

M2.73 does not claim implicit numeric coercion, literal contextual typing,
aggregate typing, reference/place checking, lowering, native self-hosting,
production promotion, performance improvement or full compiler self-hosting.
Those remain later milestones in the M2.71-M3.00 train.
