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


## D-009 — Every meaningful campaign closes its knowledge loop

Decision:

A compiler, self-hosting, correctness, performance or infrastructure campaign is not considered fully reconciled until its durable knowledge delta has been captured in the Research Lab.

The closeout must distinguish:

```text
SUCCESS
FAILURE
NEGATIVE_RESULT
INCONCLUSIVE
INFRASTRUCTURE_BLOCKER
```

and connect the result to existing Zettels/insight candidates when possible.

Reason:

During the 2026-09 native frontend/self-hosting campaign, substantial evidence accumulated in PRs #301 and #302 while the Zettelkasten remained frozen at its 2026-08 state. The implementation progressed, but the research memory did not. This creates avoidable context loss and increases the chance that future agents repeat failed lines or fail to reuse validated ideas.

Operational rule:

Do not add documentation overhead to every micro-commit. Perform knowledge closure at meaningful campaign checkpoints and campaign end, consolidating multiple milestones when they belong to one megacampaign.


## D-010 — Semantic milestone size and delivery boundary are separate

Decision:

Keep semantic/frontend milestones small enough to reason about and test, but do not require one branch/PR/report cycle for every microscopic grammar capability.

After PRs #301–#303, the native frontend moves to a larger coherent campaign:

```text
NATIVE_PROGRAM_FRONTEND
```

with internal milestones such as local binding, assignment, parameters, calls and control-flow capability as justified by the real grammar.

Reason:

The #301 → #302 → #303 sequence validated incremental semantic replacement, but repeated PR/documentation/gate overhead became disproportionate to the size of each capability.

Operational rule:

```text
SMALL_INTERNAL_MILESTONES
        !=
SMALL_PR_BOUNDARIES
```

Use focused tests per milestone, broader validation at meaningful checkpoints, and full/native qualification at campaign closure or other high-value boundaries.

Stop the larger campaign only for an architectural blocker, required redesign, scope frontier, or completed campaign objective.


## D-011 — New representation requires a reuse audit first

Decision:

```text
Before adding a new scientific-kernel value representation, audit the
existing semantic, IR, CALL, vector, reference, slice and native contracts.
Prefer direct reuse, then a narrow contract adaptation, and only then a new
representation when the existing model is factually insufficient.
```

Reason:

The native frontend campaigns already established typed scalar, vector,
reference and slice machinery. Adding a parallel scientific representation
without checking those contracts would duplicate ownership and execution
semantics and could hide whether the actual missing capability is only a math
primitive such as `sqrt`.

Operational rule:

```text
CAPABILITY_REUSE_AUDIT=REQUIRED_BEFORE_NEW_REPRESENTATION
```
