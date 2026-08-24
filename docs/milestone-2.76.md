# Milestone 2.76: Records, Enums and Fixed Layouts

M2.76 adds an S3-authored bounded contract for deterministic fixed layouts of
record scalar leaves and enum payload scalar leaves.

## Scope

The candidate accepts records with zero to eight scalar fields. The record
layout is depth-first in the supplied field order and has one fixed cell per
field. It accepts enums with one to eight variants and zero to eight scalar
payload leaves per variant. Enum layouts are tag-first and reserve one payload
cell span equal to the largest variant payload width; inactive payload slots
remain part of the fixed layout.

Each accepted layout returns its cell count and two deterministic identity
lanes. The identities include source order, field or payload type IDs, variant
order and payload widths. The S3 implementation performs the identity
calculation; the Python implementation is a differential reference.

## Evidence Contract

- S3 source: `selfhost/semantic/fixed_layout_candidate.s3`.
- Python adapter/reference: `bootstrap/s3/fixed_layout_candidate.py`.
- Focused differential contract: `tests/test_m276_fixed_layout_candidate.py`.
- Scalar type IDs are shared with M2.73: `trit=1`, `tryte=2`, `i64=3`,
  `f64=4`.
- Record field bound: 8 scalar leaves.
- Enum variant bound: 8 variants; each payload has at most 8 scalar leaves.
- Invalid bounds and unsupported scalar types fail closed.

## Non-claims

M2.76 does not claim nominal-name resolution, nested record or enum composition,
recursive layouts, constructors, layout lowering, native self-hosting,
production promotion, performance improvement or full compiler self-hosting.
Those compositions remain subsequent semantic work.
