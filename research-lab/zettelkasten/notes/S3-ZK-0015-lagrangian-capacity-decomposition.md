# S3-ZK-0015 — Register-capacity coupling may be relaxed into per-value min-cut subproblems

```text
TYPE=HYPOTHESIS
STATUS=OPEN
CREATED=2026-08-12
```

## Atomic claim

If independent per-value materialization placement is a binary cut problem but values are coupled by a shared register-capacity constraint, a Lagrangian relaxation may price register occupancy so that the relaxed problem decomposes back into independent per-value min-cuts.

## Origin

```text
NETWORK_OPTIMIZATION_BRIDGE + MATHEMATICAL_DERIVATION/HYPOTHESIS
```

Primal-dual/potential ideas motivate pricing constrained resources. The specific S3 formulation is original research.

## Candidate model

For value `v` and program point `p`:

```text
x[v,p] = 1 if value is FLEXIBLE/register-side
         0 otherwise
```

Shared capacity:

```text
sum_v x[v,p] <= K[p]
```

Original cost:

```text
sum_v placement_cost(v)
```

Introduce non-negative multiplier/price `lambda[p]`:

```text
L = original_cost
    + sum_p lambda[p] * (sum_v x[v,p] - K[p])
```

For fixed `lambda`, the value-specific term becomes:

```text
placement_cost(v)
+ sum_p lambda[p] * x[v,p]
```

which may again be solved independently per value by adding `lambda[p]` to the unary FLEXIBLE cost and running the min-cut model.

## Why this is interesting

This potentially gives:

- a dual lower bound;
- a principled 'shadow price' for scarce registers at hot points;
- decomposition into simple per-value graph problems;
- a way to measure how much shared capacity, rather than materialization itself, causes the remaining difficulty.

It does **not** prove the full compiler problem is convex/easy or that the relaxed solution is feasible.

## Connections

```text
[[S3-ZK-0005]] --relaxed-by--> [[S3-ZK-0015]]
[[S3-ZK-0007]] --can-measure--> [[S3-ZK-0015]]
[[S3-ZK-0013]] --provides-real-RA-control-for--> [[S3-ZK-0015]]
```

## Falsifier

If capacity/interference/register-class constraints cannot be approximated by useful occupancy constraints, or the duality gap is consistently too large, this is an oracle/negative result rather than a production direction.

## Experiment

Prototype integer-price subgradient updates over multiple independent materialization problems and compare:

```text
best feasible relaxed-derived solution
best dual lower bound
exact multi-value oracle optimum
```

on tiny cases.
