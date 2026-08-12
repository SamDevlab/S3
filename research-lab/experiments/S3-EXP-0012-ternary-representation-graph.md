# S3-EXP-0012 — Ternary representation conversion graph

STATUS: PLANNED

RELATED_ZETTEL:

```text
S3-ZK-0017
S3-ZK-0024
S3-ZK-0007
```

## Question

For a linear or tree-shaped trit computation, can representation selection be solved as a shortest-path/dynamic-programming problem and how large is the gap versus greedy local representation choice?

## Initial representations

Research labels only:

```text
CANONICAL_SCALAR
SIGNED_BYTE
PACKED_2BIT
VECTOR_MASK
MEMORY_CANONICAL
```

Dense base-3 should be added only after a measured memory-density experiment.

## Method

Assign operation legality and measured/estimated conversion costs. Solve tiny cases exactly; compare with a deterministic greedy heuristic.

## Measurements

```text
GREEDY_COST
OPTIMAL_COST
OPTIMALITY_GAP
CONVERSIONS
CODE_SIZE
DYNAMIC_WEIGHTED_COST
```
