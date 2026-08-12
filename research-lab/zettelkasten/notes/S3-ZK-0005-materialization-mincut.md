# S3-ZK-0005 — Restricted materialization placement may reduce to min-cut

```text
TYPE=HYPOTHESIS
STATUS=OPEN
CREATED=2026-08-12
```

## Atomic claim

For a single logical value under a binary location model, choosing where to transition between location-flexible/register-side state and canonical-memory state may be expressible as an s-t cut when costs are pairwise and constraints are hard pins.

## Origin

```text
SOURCE_DERIVED + MATHEMATICAL_HYPOTHESIS
```

Network-flow/min-cut theory supplies the optimization machinery. The mapping from compiler materialization to cuts is original S3 research and is not established by the source literature.

## Candidate encoding

For CFG/program points:

```text
R = location-flexible/register-side
M = canonical memory

R -> M edge crossing cost = store/materialize
M -> R edge crossing cost = reload/recover

hard memory requirement = pin node to M
hard register/flexible requirement = pin node to R
```

## Critical caveat

Register-capacity coupling across **multiple values** may destroy the simple binary submodular/cut structure. The one-value model may still be useful as:

- a local optimizer;
- a lower bound;
- an oracle component;
- a counterfactual cost estimator.

## Connections

```text
[[S3-ZK-0002]] --enables--> [[S3-ZK-0005]]
[[S3-ZK-0007]] --measures--> [[S3-ZK-0005]]
[[S3-ZK-0012]] --related-to--> [[S3-ZK-0005]]
```

## Falsifier

Produce a tiny single-value compiler case whose correct transition cost cannot be represented by unary pins plus pairwise cut costs without adding state that destroys the formulation.

## Experiment

Implement a generic min-cut prototype and compare it with exhaustive enumeration on every binary assignment for tiny graphs.
