# Milestone 1.12 - Fixed Arrays As First-Class Values

Status: Implementation complete; consolidated campaign validation deferred.

## Boundary

Milestone 1.12 extends the existing fixed `trit[N]` and `tryte[N]` arrays from
local frame objects to complete copy-by-value values. Length remains a positive
compile-time integer no greater than 365. Nested arrays and arrays of strings,
records, enums, or arrays remain unsupported.

The normative architecture is
[ADR-0023](decisions/ADR-0023-fixed-array-value-boundaries.md).

## Canonical Layout

`SemanticModel.fixed_value_layout(...)` is authoritative. An array contributes
one cell per element with paths `index0`, `index1`, and so on, in increasing
index order. Record fields prefix those paths with the field path. Enum payload
arrays retain the existing tag-first, maximum-payload-width enum layout.

Exact element type and length determine array compatibility. Values are always
complete; there is no partial initialization, padding, or partial group use.

## Implementation

- semantic signatures accept fixed scalar-element arrays as parameters and
  results;
- array returns use the existing IR/Assembly 0.6 result groups;
- array arguments expand to existing ordered scalar parameters;
- mutable locals remain typed memory objects;
- parameters are copied into callee-owned immutable memory before indexed use;
- whole-array assignment copies all source cells before writing the target;
- record fields and enum payloads reuse the enclosing canonical layout;
- arbitrary array-valued field expressions can be indexed through a
  compiler-owned temporary without source aliasing;
- ignored array results preserve one call and discard the complete group;
- native width-one results retain `rax`, while wider results reuse hidden sret;
- no IR or Assembly format bump is required.

## Static Gate Inventory

| Area | Classification | Evidence |
| --- | --- | --- |
| ADR | IMPLEMENTED | ADR-0023 accepted |
| ValueLayout | IMPLEMENTED | `ValueLayoutKind.FIXED_ARRAY`, ordered `indexN` cells |
| Semantic | IMPLEMENTED | signatures, exact types, complete copies, scalar-only `main` |
| Lowering | IMPLEMENTED | local memory plus complete argument/result groups |
| Verifier | NOT APPLICABLE | existing expanded scalar parameter/result checks are authoritative |
| Optimizer | NOT APPLICABLE | existing call/result group preservation applies unchanged |
| SSA | NOT APPLICABLE | array cells use existing scalar SSA/group contracts |
| Emulator | NOT APPLICABLE | existing registers, tuples, memory, and bounds execute the lowering |
| Native | NOT APPLICABLE | existing argument stack path and hidden sret consume expanded groups |
| Imports | IMPLEMENTED | module type rewriting preserves `ArrayType`; expanded signatures are deterministic |
| Documentation | IMPLEMENTED | language, memory, composite, architecture, roadmap, and this plan |
| Tests authored | IMPLEMENTED | focused hosted and native boundary coverage |

## Coverage Status

Coverage has been authored for canonical layout, `trit`/`tryte` parameters and
results, length/type mismatch, whole-value copying, record fields, enum
payloads, recursion, nested calls, ignored results, O0/O1, emulator, native
width 8, bounds inherited from the existing array corpus, and aggregate
`main` rejection.

CREATED - NOT EXECUTED UNTIL CAMPAIGN IMPLEMENTATION COMPLETION

## Deferred Validation

No test, compiler execution, emulator, native harness, benchmark, golden tool,
renderer comparison, or CI query was run while implementing this milestone.
Those checks remain deferred until Milestone 1.16 closes the campaign-wide
implementation gate.

MILESTONE 1.12 - IMPLEMENTATION COMPLETE

CONSOLIDATED VALIDATION DEFERRED
