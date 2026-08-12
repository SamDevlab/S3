# Durable Research Decisions

## D-001 — Use a long-lived branch rather than a direct production branch

Decision:

```text
research/zettelkasten-lab-20260812
```

Reason:

Research must survive chat migrations and may contain prototypes/negative results that should never be merged wholesale into production.

## D-002 — Research branch never merges directly to main

Promoted ideas are ported to a fresh feature branch from then-current `origin/main`.

Reason:

Prevents stale production code and research-only artifacts from contaminating the release history.

## D-003 — Zettelkasten is the durable knowledge layer

Atomic notes are preferred over monolithic literature summaries.

Reason:

We want new ideas to emerge from links between compiler evidence, program analysis, order/lattice theory, network optimization, and combinatorial optimization.

## D-004 — Negative results are permanent

Do not delete failed mathematical hypotheses.

Reason:

A minimal counterexample is reusable research knowledge and prevents repeated dead ends after context migrations.

## D-005 — Mathematical algorithms may be used as oracles

An exponential/ILP/constraint approach may exist in the lab even if it can never ship.

Reason:

Knowing the exact optimum on tiny cases provides an objective benchmark for production heuristics.

## D-006 — Do not assume RA is the primary bottleneck

A frame access is not called a spill unless the allocation decision actually created it.

Reason:

P3 evidence established broader pre-RA/default-path canonicalization while true RA spill dominance remained unproven.

## D-007 — Preserve location flexibility as a first-class research property

Research should measure where a logical value loses future representation options.

Reason:

P1–P3 suggest optimizing late emitted moves has limited coverage when the representation was already collapsed earlier.

## D-008 — P4 remains unnamed at production level until research selects a winner

The broad research umbrella is `global-value-residency-and-memory-materialization`.

The production milestone should later use the precise winning capability name.

Reason:

Avoid roadmap-driven confirmation bias.
