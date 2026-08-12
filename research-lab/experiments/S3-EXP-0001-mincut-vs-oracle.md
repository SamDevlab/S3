# S3-EXP-0001 — Binary min-cut vs exact oracle

```text
STATUS=PLANNED
RELATED_ZETTEL=S3-ZK-0005,S3-ZK-0007
```

## Question

Inside the explicitly restricted binary model, does the directed s-t cut encoding always produce the same optimum as exhaustive enumeration?

## Model

Per program point one binary decision:

```text
FLEXIBLE
MEMORY
```

Costs:

```text
unary flexible cost
unary memory cost
FLEXIBLE -> MEMORY transition = materialize/store
MEMORY -> FLEXIBLE transition = recover/load
hard pins
```

No shared register-capacity coupling.

## Prototype

```text
research-lab/prototypes/materialization_cut.py
research-lab/prototypes/exact_oracle.py
```

## Minimum execution

```bash
python research-lab/prototypes/demo.py
```

The demo currently performs deterministic randomized cross-checks.

## Expanded experiment

Run multiple deterministic seeds, increasing graph size only while exhaustive oracle cost is manageable.

Suggested matrix:

```text
seeds: 100
cases/seed: 1000
nodes: 1..10
random directed transition density: several values from 0 to 0.8
unary costs: 0..20
transition costs: 0..20
pins: 0%, 10%, 30%, 60%
```

## Gate

```text
MINCUT_ORACLE_MISMATCHES=0
```

within the stated model.

Any mismatch must preserve the smallest known counterexample before fixing code/model.

## Research boundary

Success proves only the binary pairwise energy encoding. It does not prove that general multi-value register allocation or capacity-constrained residency is reducible to min-cut.
