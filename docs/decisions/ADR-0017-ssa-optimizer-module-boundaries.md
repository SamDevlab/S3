# ADR-0017: SSA optimizer module boundaries

- Status: accepted
- Date: 2026-07-31

## Context

The O1 optimizer grew from a single implementation module into a correctness
boundary for SSA construction, pass orchestration, and de-SSA lowering. ADR-0016
defines the semantic proof requirements for that pipeline. The code now needs a
matching module layout so future optimizer work can be reviewed by pass family
without weakening the public compiler surface.

S3 still has no public SSA format. Phi nodes, SSA pass contracts, pass results,
and optimizer telemetry remain internal implementation details.

## Decision

The public compatibility facade remains `bootstrap.s3.ssa_opt`. Existing tests
and compiler code may continue importing the established pass names from that
module.

Pass implementations live under `bootstrap.s3.ssa_optimizer`:

- `contracts.py` owns `SSAPassContract`, `PassResult`, and the active O1 pass
  inventory.
- `common.py` owns shared opcode sets and width helpers.
- `lowering.py` owns SSA-to-IR lowering and CFG reconstruction from SSA blocks.
- `propagation.py` owns constant propagation and copy propagation.
- `value_numbering.py` owns CSE and GVN.
- `elimination.py` owns DCE, ADCE, and DSE.
- `loops.py` owns LICM and strength reduction.
- `sccp.py` owns sparse conditional constant propagation.
- `peephole.py` owns local SSA peephole rewrites.

The fixpoint loop consumes `PassResult` values. Convergence remains defined by
real structural change in the returned SSA function, not by counters. Telemetry
is accumulated only when a pass result changes the SSA structure.

## Consequences

Positive consequences:

- pass ownership is explicit;
- active O1 pass order has a single internal source of truth;
- future pass additions must declare contracts before entering the fixpoint
  pipeline;
- the old `ssa_opt` import surface remains stable for current compiler and
  tests;
- optimizer review can focus on one pass family at a time.

Negative consequences:

- some imports are intentionally conservative during the split;
- `ssa.py` remains a module, so the optimizer package must use
  `ssa_optimizer` rather than `ssa`.

## Alternatives considered

**Keep every pass in `ssa_opt.py`.** Rejected because it concentrates unrelated
optimizer responsibilities in one large file and makes future correctness
reviews harder.

**Rename `ssa.py` into a package.** Rejected for this milestone because it would
be a broader compatibility change unrelated to optimizer semantics.

**Expose SSA optimizer APIs publicly.** Rejected because SSA remains an internal
optimization representation, not a stable user-facing format.
