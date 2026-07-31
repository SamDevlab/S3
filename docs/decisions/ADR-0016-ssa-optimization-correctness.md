# ADR-0016: SSA optimization correctness contracts

- Status: accepted
- Date: 2026-07-31

## Context

The S3 O1 pipeline uses SSA as an internal optimization representation. Milestones 0.60-0.95 added SSA construction, Phi placement, several SSA passes, de-SSA lowering, and O1 telemetry. That infrastructure must now be treated as correctness-critical rather than as best-effort optimization scaffolding.

Incorrect optimization is worse than missed optimization. The compiler must preserve O0/O1 functional equivalence, verifier validity, memory initialization safety, and native execution semantics.

## Decision

SSA remains internal. S3 source, public IR, and public S3 Assembly do not expose Phi nodes.

O1 transformations must be conservative. If a pass cannot prove that a transformation preserves semantics, it must leave the program unchanged.

### Alias and memory operations

Memory optimizations require explicit alias proof.

The current alias analysis is frame-local and cell-oriented. It reasons about:

- memory object identity;
- constant indices;
- SSA index values;
- unknown indices;
- the current absence of pointers in S3.

Alias results are normative:

- `NoAlias` means two references cannot observe the same cell.
- `MustAlias` means two references are proved to observe the same cell.
- `MayAlias` means proof is absent or incomplete.

Absence of proof implies `MayAlias`. A `MayAlias` result blocks destructive memory optimizations such as dead store elimination.

Memory SSA may exist as analysis infrastructure, but a pass may cite it as proof only when it actually consumes relationships modeled by Memory SSA. Until Memory SSA models control flow, memory phis, load-to-def relationships, and unknown calls sufficiently, DSE remains local and alias-analysis based.

### de-SSA and Phi lowering

Phi lowering is implemented with edge-specific copies. Copies that must occur only on one successor edge of a multi-target terminator require a deterministic split block.

The verified IR still enforces single-definition registers. Therefore, Phi lowering must not emit multiple predecessor writes to the same result register. The lowering uses internal one-cell mutable buffers for Phi values:

- each Phi target receives a distinct internal buffer;
- predecessor edges store the selected incoming value;
- the successor block loads the selected value once into the Phi target register.

This preserves parallel-copy semantics, including swaps and longer cycles, because incoming values are captured into distinct buffers before the successor consumes them.

Split block names and emitted copy order must be deterministic.

### Verification and convergence

Each active O1 pass must preserve SSA or be explicitly treated as the final de-SSA conversion.

The fixpoint loop must decide convergence from real structural change in the returned SSA function. Counters, candidate counts, or replacement attempts are not sufficient.

Internal verification may validate SSA between passes and verify the final de-SSA IR. This is not a public CLI option.

Telemetry is diagnostic, not proof. Metrics may help explain what changed, but they do not replace functional equivalence, verifier checks, initialization analysis, native differential testing, or focused regression tests.

Telemetry fields must represent transformations that actually occurred. Zero must mean that no transformation of that kind was observed.

## Consequences

Positive consequences:

- DSE can no longer remove stores based on uncertain dynamic indices.
- Phi lowering no longer depends on invalid multi-definition moves.
- Critical edge splits are explicit and deterministic.
- O1 convergence no longer depends on false counters.
- Tests can ablate individual O1 passes without exposing public flags.

Negative consequences:

- Some safe optimizations remain intentionally disabled until stronger proof exists.
- Phi lowering may introduce internal memory objects and edge blocks.
- Memory SSA remains limited until a future milestone extends it into a full memory-flow proof.

## Alternatives considered

**Keep predecessor MOVE lowering for Phis.** Rejected because the verified IR enforces single definitions; writing the same Phi target from multiple predecessors creates invalid IR and mishandles target-specific branch edges.

**Relax the IR verifier for non-SSA output.** Rejected because it would weaken an existing correctness boundary and risk hiding optimizer errors.

**Use Memory SSA as a nominal DSE dependency.** Rejected until Memory SSA models enough CFG and memory-flow detail to justify destructive memory transformations.

**Use counters as fixpoint evidence.** Rejected because counters can count candidates or attempts that did not change the returned function.

## Status of future work

Future milestones may implement Memory GVN, global DSE, register-copy based de-SSA, or more precise Memory SSA, but each requires its own proof and tests. This ADR does not authorize new optimizations by itself.
