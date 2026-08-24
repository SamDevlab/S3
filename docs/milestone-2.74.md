# Milestone 2.74: Bounded Place and Reference Checks

M2.74 adds an S3-authored contract for the readable, writable, addressable and
reference-mutability decisions needed by the semantic self-hosting subset.

## Scope

The bounded descriptor models a scalar place or reference with one of three
storage classes: `value`, `shared_ref` or `mutable_ref`. Operations cover read,
write, shared and mutable address creation, shared and mutable dereference, and
shared or mutable reborrow. Every operation returns an exact result type and
result storage class, or a stable rejection code.

Mutable reference creation and reborrow require a writable place. Mutable
dereference and mutable reborrow require a mutable reference. Shared operations
cannot be used to obtain a mutable capability. Reads and shared dereferences
also require an initialized, readable place.

## Evidence Contract

- S3 source: `selfhost/semantic/place_reference_candidate.s3`.
- Python adapter/reference: `bootstrap/s3/place_reference_candidate.py`.
- Focused contract: `tests/test_m274_place_reference_candidate.py`.
- Scalar type IDs are shared with M2.73.
- Place kind IDs: `value=1`, `shared_ref=2`, `mutable_ref=3`.
- Invalid operations, types, kinds and flag shapes fail closed.
- Python remains the reference/default compiler path.

## Non-claims

M2.74 does not claim full borrow checking, lifetime inference, aggregate field
provenance, escape analysis, lowering, native self-hosting, production
promotion, performance improvement or full compiler self-hosting.
