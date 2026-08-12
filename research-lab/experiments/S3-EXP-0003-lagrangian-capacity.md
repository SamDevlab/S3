# S3-EXP-0003 — Lagrangian decomposition for shared register capacity

```text
STATUS=PLANNED
RELATED_ZETTEL=S3-ZK-0005,S3-ZK-0007,S3-ZK-0015
```

## Question

Can a shared per-point FLEXIBLE/register-capacity constraint be relaxed with non-negative prices so each value again solves an independent min-cut problem, while producing useful dual bounds and near-feasible/primal placements?

## Prototypes

```text
lagrangian_capacity.py
multivalue_oracle.py
capacity_demo.py
```

## First check

```bash
python research-lab/prototypes/capacity_demo.py
```

The first deliberately symmetric case distinguishes:

```text
exact primal optimum
Lagrangian dual lower bound
best feasible point found by independent priced subproblems
```

This matters because a tight dual bound does not imply the decomposed primal assignments automatically satisfy capacity optimally.

## Expanded matrix

For tiny exact-oracle-compatible problems vary:

```text
values: 2..5
nodes: 1..5
capacity: 1..K
transition density
unary memory/flexible costs
materialize/recover costs
pins
```

Measure:

```text
EXACT_OPTIMUM=
BEST_DUAL_BOUND=
DUALITY_GAP=
BEST_FEASIBLE_COST=
PRIMAL_GAP=
ITERATIONS=
PRICE_VECTOR=
```

## Success modes

Even if not production-suitable, the model is useful if it provides one or more of:

- tight lower bounds;
- evidence that register capacity is/is not the hard coupling;
- good prices for a later heuristic;
- a principled decomposition baseline.

## Rejection

Reject as production direction if the dual/primal gaps are consistently poor or if realistic interference/register-class constraints cannot be represented without destroying the decomposition.
