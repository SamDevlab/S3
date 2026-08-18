# M1.61 Architecture Preflight

## Findings

- `i64_map` and `i64_set` are nominal, deterministic, insertion-ordered
  collections with fixed native cell widths.
- M1.55 already performs closed source specialization before semantic
  analysis, so generic collection syntax can reuse that boundary.
- The existing native ABI has no runtime type descriptors and the hosted
  collection helpers enforce the i64 representation.

## Decision

Implement a closed V1 alias: `map<i64, i64>` specializes to `i64_map` and
`set<i64>` specializes to `i64_set`. Generic operation names specialize to
the existing builtins. Reject other domains explicitly until a separate
representation decision exists.

## Safety and compatibility

This preserves the established ownership, borrow, capacity, insertion-order,
duplicate, replacement, and native lowering contracts. It does not introduce
traits, runtime generic metadata, or a second collection implementation.

## Gate

The implementation gate is focused M1.61 coverage plus the existing ordered
collection regression tests and native lowering checks. No global T4 is part
of this campaign.
