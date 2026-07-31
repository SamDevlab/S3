# Milestone 0.98 - Optimizer Architecture

## Goal

Make the existing O1 optimizer easier to audit and extend without changing S3
language behavior, public IR, S3 Assembly, ABI, CLI flags, goldens, baselines, or
the public version.

## Delivered

- `bootstrap.s3.ssa_opt` remains the compatibility facade for existing imports.
- SSA optimization passes are split under `bootstrap.s3.ssa_optimizer` by
  responsibility: contracts, common helpers, lowering, propagation, value
  numbering, elimination, loops, SCCP, and peephole rewrites.
- `SSAPassContract` and `SSA_PASS_CONTRACTS` define the active O1 pass inventory
  and pass boundaries.
- `PassResult` standardizes how the fixpoint loop receives a transformed SSA
  function, structural-change status, and optional telemetry.
- The fixpoint loop still decides convergence from the returned SSA structure,
  preserving ADR-0016.
- Focused SSA, optimizer, and differential tests cover the split.

## Non-goals

- no new source syntax;
- no new optimization pass;
- no public SSA format;
- no module/import language feature;
- no record/enum feature;
- no self-hosted runtime component;
- no golden or baseline update.

## Validation

The milestone is validated by focused tests for:

- SSA pass contracts;
- fixpoint pipeline convergence;
- existing SSA optimization passes;
- de-SSA lowering;
- hosted O0/O1 differential matrix.
