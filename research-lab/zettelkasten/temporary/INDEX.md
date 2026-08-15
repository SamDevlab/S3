# S3 Zettelkasten — Temporary Notes Index

```text
DATE=2026-08-15
LIFECYCLE=TEMPORARY
CANONICAL_NOTE_FILES=../notes/S3-ZK-*.md
COUNT=24
```

Temporary notes are active research objects, not discarded notes. They remain canonical under `../notes/` and keep their permanent IDs.

A note stays temporary while its central claim is open, speculative, inconclusive, superseded as current-state knowledge, or still awaiting a bounded falsifiable validation.

## Open hypotheses / questions

| ID | Current role | Open question / hypothesis |
|---|---|---|
| [[S3-ZK-0003]] | HYPOTHESIS | Does value representation admit a useful residence lattice for S3? |
| [[S3-ZK-0004]] | HYPOTHESIS | Should representation facts compose as a reduced product domain? |
| [[S3-ZK-0005]] | HYPOTHESIS | Does a restricted materialization-placement problem reduce to min-cut/min-cost flow? |
| [[S3-ZK-0007]] | HYPOTHESIS | Can tiny-CFG exact optimization provide a useful optimality oracle? |
| [[S3-ZK-0008]] | QUESTION | Do restricted feasible resident sets have matroid-like exchange structure? |
| [[S3-ZK-0012]] | QUESTION | Is residence benefit submodular in any useful restricted domain? |
| [[S3-ZK-0014]] | HYPOTHESIS | Does lazy materialization require paired forward-availability and backward-necessity analyses? |
| [[S3-ZK-0015]] | HYPOTHESIS | Can shared register-capacity coupling be relaxed into priced per-value cut subproblems? |
| [[S3-ZK-0018]] | HYPOTHESIS | Is there a cost-optimal ternary operation basis for a relevant target/corpus? |
| [[S3-ZK-0019]] | HYPOTHESIS | Can semantic finite/ternary control states be profitably minimized before binary branch lowering? |
| [[S3-ZK-0021]] | HYPOTHESIS | Can compiler information loss be measured in a way that predicts actionable downstream opportunity? |
| [[S3-ZK-0023]] | HYPOTHESIS | Would a ternary virtual ISA preserve enough useful semantics to justify its complexity? |
| [[S3-ZK-0024]] | HYPOTHESIS | Can ternary representation selection be modeled usefully as a conversion-graph optimization problem? |
| [[S3-ZK-0025]] | HYPOTHESIS | Can a deliberately bounded compiler proof language preserve high-value facts cheaply? |

## Open bridges / architecture proposals

These ideas are plausible and connected to supported knowledge, but the architecture itself is not yet validated.

| ID | Current role | Open architecture connection |
|---|---|---|
| [[S3-ZK-0009]] | ARCHITECTURE | Study compiler quality as preservation/loss of future representation choices. |
| [[S3-ZK-0010]] | BRIDGE | Introduce approximation only where it buys convergence or bounded cost. |
| [[S3-ZK-0016]] | ARCHITECTURE | Keep ternary semantics distinct from physical encoding until commitment is justified. |
| [[S3-ZK-0017]] | BRIDGE | Generalize location flexibility into representation flexibility. |
| [[S3-ZK-0020]] | BRIDGE | Use partition information to lower-bound future-state dependencies. |
| [[S3-ZK-0022]] | ARCHITECTURE | Preserve selected optimization facts as explicit bounded proof/fact objects. |
| [[S3-ZK-0027]] | BRIDGE | Define lowering boundaries by the downstream facts they must preserve. |

## Superseded / unresolved historical notes

| ID | State | Reason for temporary classification |
|---|---|---|
| [[S3-ZK-0042]] | SUPERSEDED_AS_CURRENT_LIMITATION | The O1 slice verifier/correctness limitation was later fixed and recorded by [[S3-ZK-0045]]. Keep only as provenance of the earlier state. |
| [[S3-ZK-0043]] | OPEN_NEGATIVE_RESULT | Frame metadata slot reuse was not observed, but the negative result did not close the broader hypothesis with sufficient proof. |
| [[S3-ZK-0079]] | OPEN_QUESTION | Under which exact S3 semantic and memory-effect conditions can the localized parser-loop operations be proven reusable or unnecessary? |

## Promotion requirements

A temporary note becomes permanent only after its atomic claim is narrowed enough to have:

```text
EVIDENCE
SCOPE
FALSIFIER_OR_REOPEN_CONDITION
PROVENANCE
CONFLICT_RECONCILIATION
```

For architecture notes, an attractive design is not enough. At least one bounded compiler problem must demonstrate that the architecture resolves a real correctness, analysis or performance limitation without violating existing contracts.

For mathematical hypotheses, exact bounded oracles are welcome, but resemblance to a known mathematical structure is not proof that S3 instantiates that structure.

## Research priority rule

Temporary-note count is not a research queue.

Do not investigate all open notes.

Select a temporary note only when current compiler evidence creates a discriminating question with meaningful expected value.
