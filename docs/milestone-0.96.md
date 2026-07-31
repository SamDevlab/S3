# Milestone 0.96 - O1 SSA Pipeline Stabilization

Status:
In progress

## Objective

Stabilize and prove the SSA/O1 infrastructure added across milestones 0.60-0.95 without introducing new optimizations.

## Subdivisions

- 0.96-A - GVN, CSE, and metadata preservation.
- 0.96-B - Memory SSA, Alias Analysis, and DSE.
- 0.96-C - de-SSA, Phi lowering, and critical edges.
- 0.96-D - telemetry, O0/O1 differentials, and native coverage.

## 0.96-A Scope

GVN previously calculated substitutions but applied copy propagation to the original SSA function. As a result, telemetry could report eliminations without an observable change in the returned function.

GVN also considered LOAD eligible without Memory GVN proof. For this milestone, LOAD remains ineligible.

CSE manually reconstructed SSAFunction and lost return_type, causing TRIT functions to fall back to the default TRYTE return type.

This delivery fixes those contracts. CSE remains outside O1, and no new optimization is introduced.

## 0.96-A Completion Criteria

- GVN transformations are present in the returned function.
- Dominance is covered by regression tests.
- Sibling branches remain isolated.
- LOAD is ineligible for GVN.
- GVN telemetry matches actual instruction removal.
- SSAFunction metadata is preserved.
- Public O0/O1 equivalence is covered.
- Full CI and native-x86-64 validation are green.

## Out of Scope

- CSE integration into O1.
- Memory GVN.
- DSE changes.
- LICM changes.
- SCCP changes.
- ADCE changes.
- de-SSA changes.
- Public format changes.
- New language features.
