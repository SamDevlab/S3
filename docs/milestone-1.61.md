# Milestone 1.61 - Generic Ordered Map and Set V1

## Architecture status

M1.61 adds generic spellings for the existing deterministic ordered
collection ABI. The first bounded specialization is `map<i64, i64>` and
`set<i64>`, which lower directly to the established `i64_map` and `i64_set`
families. This keeps ordering, capacity, replacement, duplicate, clone, move,
borrow, and drop behavior identical to M1.41.

The compiler rejects other map/set type arguments during generic
specialization. This is intentional: the current native descriptor has fixed
8-byte collection cells and no runtime type metadata. Owned and parametric
aggregate elements remain future extensions rather than being erased into an
unsafe representation.

## Public surface

- `map<i64, i64>` with `map_*<i64, i64>` builtins;
- `set<i64>` with `set_*<i64>` builtins;
- existing `i64_map` and `i64_set` names remain compatible.

## Out of scope

General traits, hashing, runtime reflection, hidden allocation, arbitrary
owned collection elements, and public raw pointers remain out of scope.

## Validation

Focused tests cover generic syntax, ordered replacement and duplicate
semantics, O0/O1 execution, native symbol lowering, and static rejection of
unsupported domains. Broader cross-subsystem closure is recorded under
`reports/roadmap-1.61-1.70-execution/m1.61/`.

## Dependency

M1.62 may build on the existing borrow model without depending on a wider
generic collection representation.

## Implementation and environment status

COMPLETE for the bounded `i64` specialization. Hosted, O0/O1, and native
lowering gates pass; Linux native execution is `DEFERRED_BY_ENVIRONMENT`.
