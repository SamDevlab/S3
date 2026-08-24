# Milestone 2.75: Bounded Function Signatures and Calls

M2.75 adds an S3-authored contract for bounded function declarations and
type-checked calls in the semantic self-hosting subset.

## Scope

The candidate accepts at most eight function declarations and at most eight
parameters per declaration. Each declaration has a tryte function identifier,
an exact ordered scalar parameter-type sequence and one scalar return type.
Calls resolve by exact function identifier, exact arity and exact parameter
types. Accepted calls return the declared scalar type; unknown identifiers,
arity mismatches, type mismatches and invalid declarations return stable
rejection codes.

The S3 candidate stores each declaration's parameter types in a fixed eight
slot block. Invalid bounds, duplicate function identifiers, unsupported scalar
types and malformed Python adapter inputs fail closed before candidate
execution.

## Evidence Contract

- S3 source: `selfhost/semantic/function_call_candidate.s3`.
- Python adapter/reference: `bootstrap/s3/function_call_candidate.py`.
- Focused differential contract: `tests/test_m275_function_call_candidate.py`.
- Scalar type IDs are shared with M2.73: `trit=1`, `tryte=2`, `i64=3`,
  `f64=4`.
- Maximum function declarations: 8.
- Maximum parameters per declaration and call: 8.
- The Python path remains the reference/default compiler path.

## Non-claims

M2.75 does not claim function-body lowering, calling-convention support,
closures, generic functions, recursion, native self-hosting, production
promotion, performance improvement or full compiler self-hosting.
