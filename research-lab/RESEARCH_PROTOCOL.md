# S3 Research Protocol

## Objective

Turn compiler observations, literature concepts, mathematical models, and experiment results into durable, linkable knowledge that can survive conversation boundaries and drive production milestones.

## Zettelkasten lifecycle

```text
SOURCE OBSERVATION
    ↓
ATOMIC NOTE
    ↓
LINKS / BRIDGES
    ↓
FALSIFIABLE HYPOTHESIS
    ↓
EXPERIMENT
    ↓
SUPPORTED / REJECTED / INCONCLUSIVE
    ↓
ARCHITECTURAL PROPOSAL
    ↓
PRODUCTION MILESTONE
```

Do not jump from literature directly to production code.

## Atomicity rule

Each note should assert one main idea. If a note requires several independent claims, split it.

Good:

```text
S3-ZK-0002: Materialization is a decision, not a default state.
```

Too broad:

```text
Everything about register allocation, data flow, phi nodes and network flows.
```

## Evidence classes

Each claim should distinguish:

```text
SOURCE_DERIVED
S3_MEASURED
S3_CODE_INSPECTION
MATHEMATICAL_DERIVATION
INFERENCE
HYPOTHESIS
```

Do not silently upgrade an inference into a measured fact.

## Link types

Use explicit relationship tags where useful:

```text
supports
contradicts
generalizes
specializes
requires
enables
motivates
measures
falsifies
alternative-to
```

Example:

```text
[[S3-ZK-0003]] --enables--> [[S3-ZK-0004]]
```

## Hypothesis quality gate

A hypothesis should state:

```text
CLAIM
WHY_IT_MIGHT_BE_TRUE
WHAT_WOULD_FALSIFY_IT
MEASUREMENT
EXPECTED_GENERALITY
RISK
```

## Mathematical-model gate

Before introducing a mathematical model into production, answer:

1. What are the objects?
2. What are the variables/states?
3. What are the constraints?
4. What is the objective?
5. Is the solution exact, conservative, approximate, or heuristic?
6. Is correctness dependent on optimality, or only on feasibility?
7. What is the worst-case complexity?
8. Can it fail safely to the current compiler behavior?
9. What simpler model competes with it?
10. What measured S3 problem does it solve?

## Formal-analysis gate

For data-flow / abstract-interpretation style analyses record:

```text
DOMAIN=
ORDER=
BOTTOM=
TOP=
MEET_OR_JOIN=
TRANSFER_FUNCTIONS=
BOUNDARY_CONDITION=
DIRECTION=FORWARD/BACKWARD
MONOTONE=YES/NO/UNKNOWN
FINITE_HEIGHT=YES/NO
CONVERGENCE_MECHANISM=
SAFETY_INTERPRETATION=
```

If widening/narrowing is used, precision/cost tradeoffs must be measured.

## Graph-optimization gate

For min-cut/min-cost-flow/matching/matroid formulations record:

```text
GRAPH_OBJECT=
VERTEX_MEANING=
EDGE_MEANING=
CAPACITY_MEANING=
COST_MEANING=
HARD_CONSTRAINT_ENCODING=
SOLUTION_TO_COMPILER_MAPPING=
INTEGRALITY_REQUIREMENT=
COUNTEREXAMPLE_SEARCH=
```

Do not force a graph formulation when higher-order coupling invalidates it.

## Oracle principle

Expensive exact algorithms are allowed in this lab when they serve as an oracle.

A useful oracle answers:

```text
What is the best possible cost under a clearly defined simplified model?
```

Then compare:

```text
BASELINE_COST
HEURISTIC_COST
ORACLE_COST
OPTIMALITY_GAP
```

The oracle is not automatically production code.

## Negative-result protocol

A rejected idea should create a note containing:

```text
MODEL=
COUNTEREXAMPLE=
WHY_IT_FAILS=
SCOPE_WHERE_IT_STILL_WORKS=
CAN_IT_BE_AN_ORACLE=
DO_NOT_RETRY_UNLESS=
```

Do not delete failed experiments.

## Production-promotion gate

No research change should be ported to production until:

```text
PROBLEM_MEASURED=YES
MODEL_VALIDATED=YES
CORRECTNESS_ARGUMENT=COMPLETE
PROTOTYPE=PASS
NEGATIVE_CASES=PASS
OPPORTUNITY_COVERAGE=MEASURED
CROSS_WORKLOAD_GENERALITY=YES
COMPILE_TIME_COST=ACCEPTABLE
SIMPLER_ALTERNATIVES_COMPARED=YES
```

Then create a fresh production branch from current `origin/main`.

## Session-end protocol

Before ending a major research session:

1. update `STATE.json`;
2. update `HANDOFF.md` if production/research direction changed materially;
3. add or revise Zettelkasten notes;
4. record negative results;
5. ensure prototype entry points still run;
6. leave `NEXT_ACTIONS` explicit;
7. do not rely on chat memory as the only source of truth.
