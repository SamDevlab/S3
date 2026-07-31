# Milestone 0.96 - O1 SSA Pipeline Stabilization

Status:
Implementation complete for 0.96-A, 0.96-B, 0.96-C, and 0.96-D.

## Objective

Stabilize the SSA/O1 infrastructure added across milestones 0.60-0.95 without introducing new optimizations or changing public syntax, IR format, S3 Assembly format, ABI, goldens, or benchmark baselines.

The milestone treats correctness as the optimization gate: when a transformation cannot be proved safe, O1 must preserve the original structure instead of speculating.

## Subdivisions

- 0.96-A - GVN, CSE, and metadata preservation.
- 0.96-B - Memory SSA, Alias Analysis, and DSE.
- 0.96-C - de-SSA, Phi lowering, and critical edges.
- 0.96-D - verification between passes, convergence, telemetry, and pass ablation.

## 0.96-A - Completed Foundation

GVN now returns the transformation it actually computes. LOAD remains ineligible for GVN because the current optimizer does not implement Memory GVN proof.

CSE preserves `SSAFunction` metadata such as `return_type`; it remains outside the O1 pipeline.

GVN telemetry counts instructions actually removed from the returned SSA function.

## 0.96-B - Memory Safety for DSE

Alias Analysis now defines cell-level results:

- `NoAlias`: two memory references cannot observe the same frame-local cell.
- `MustAlias`: two memory references are proved to observe the same frame-local cell.
- `MayAlias`: proof is absent or incomplete, so the references must be treated as potentially overlapping.

The analysis covers the current S3 memory model: frame-local memory objects, constant indices, SSA index values, unknown indices, and absence of pointers. It does not claim general pointer analysis.

Memory SSA remains available as construction/diagnostic infrastructure, but DSE no longer invokes it as a nominal proof. The DSE implementation is explicitly local and conservative.

DSE may remove a store only when a later store in the same basic block is proved to `MustAlias` the same cell and no intervening observable `LOAD` or unknown `CALL` can observe the earlier value.

DSE preserves stores when:

- memory objects differ;
- constant cell indices differ;
- dynamic SSA indices are not proved equal;
- a `LOAD` may observe the previous value;
- an unknown `CALL` may observe or modify memory;
- stores occur on sibling control-flow paths;
- the store may be the only initialization before a read.

Telemetry counts stores actually removed and does not count rejected candidates.

## 0.96-C - de-SSA and Phi Lowering

Phi nodes remain an internal SSA representation. No Phi appears in public IR, public S3 Assembly, or source syntax.

The de-SSA lowering now uses edge-specific copies. Because the current verified IR preserves single-definition registers, Phi values are lowered through internal one-cell mutable memory buffers:

- incoming edge copies store the selected value into a Phi buffer;
- the Phi block loads the buffer once into the Phi target register;
- each Phi receives its own buffer and preserves its element type.

This strategy preserves parallel-copy semantics by construction. Multiple Phis in the same successor store into distinct buffers before the successor loads them, so swaps and longer copy cycles do not overwrite a pending source.

When a Phi copy belongs to a specific successor edge of a multi-target terminator, the lowering creates a deterministic split block named from the predecessor and successor. The original terminator target is rewritten to the split block, and the split block stores the edge copies before jumping to the original successor.

The lowering preserves:

- explicit `entry` block ordering;
- function `return_type`;
- TRIT and TRYTE Phi types;
- function parameters used as Phi operands;
- unreachable blocks that contain Phis;
- verifier-valid IR after de-SSA.

## 0.96-D - Verification, Convergence, and Telemetry

The fixpoint pipeline now derives `changed` from deterministic structural comparison of the SSA function before and after each pass. Counters alone no longer drive convergence.

The pipeline has internal, test-only pass ablation through `disabled_passes`, covering the active O1 passes:

- GVN;
- copy propagation;
- DSE;
- DCE;
- ADCE;
- LICM;
- SCCP;
- strength reduction;
- peephole.

The internal `verify_each_pass` mode validates SSA after each pass and verifies the final de-SSA IR. It is not exposed as a public CLI flag.

Telemetry now records only observable transformations:

- `expressions_eliminated`;
- `stores_removed`;
- `dead_instructions_removed`;
- `licm_moves`;
- `strength_reductions`;
- `branches_removed`;
- real iteration count;
- `converged`;
- `max_iterations_reached`.

A previous strength-reduction counter incremented for repeated-addition candidates without changing the SSA function. That false count was removed; the pass now counts only transformations it actually emits.

## Conservative Decisions

- CSE remains outside O1.
- LOAD remains outside GVN.
- DSE remains intra-block.
- Memory SSA is not used as proof until it models CFG, memory phis, load-to-def relationships, and unknown calls sufficiently.
- No new optimization was added to complete this milestone.

## Out of Scope

- Public syntax changes.
- Public IR or S3 Assembly format changes.
- ABI changes.
- Backend contract changes.
- Golden or benchmark baseline updates.
- CSE integration into O1.
- Memory GVN.
- Global DSE.
- Interprocedural optimization.
- New language features.
