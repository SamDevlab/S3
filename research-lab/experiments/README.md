# Experiment Registry

Every serious hypothesis should receive a durable experiment record before production promotion.

Suggested IDs:

```text
S3-EXP-0001
S3-EXP-0002
...
```

## Initial queue

### S3-EXP-0001 — Binary min-cut validity

Related:

```text
[[S3-ZK-0005]]
[[S3-ZK-0007]]
```

Goal:

Cross-check the min-cut binary materialization solution against exhaustive enumeration over hundreds/thousands of deterministic tiny problems.

Success:

```text
MINCUT_COST == EXACT_ORACLE_COST
```

for every problem inside the model assumptions.

Failure:

Preserve the minimal counterexample and correct/reject the graph encoding.

### S3-EXP-0002 — Register-capacity coupling counterexample

Related:

```text
[[S3-ZK-0005]]
```

Goal:

Introduce two or more values sharing K registers and determine the smallest case where independently optimal per-value cuts become jointly infeasible/suboptimal.

Expected value:

This should define the exact boundary between the elegant single-value cut model and the richer multi-value problem.

### S3-EXP-0003 — Residence-domain laws

Related:

```text
[[S3-ZK-0003]]
[[S3-ZK-0004]]
[[S3-ZK-0011]]
```

Goal:

Exhaustively verify order/join/meet laws and transfer monotonicity for candidate finite residence domains.

### S3-EXP-0004 — S3 location-flexibility loss histogram

Related:

```text
[[S3-ZK-0001]]
[[S3-ZK-0006]]
[[S3-ZK-0009]]
```

Goal:

Trace real S3 logical values through:

```text
SSA -> SSA destruction -> Assembly IR -> frame planning -> RA -> emitter
```

and record the first layer where each value becomes memory-only.

### S3-EXP-0005 — Matroid exchange counterexample search

Related:

```text
[[S3-ZK-0008]]
```

Goal:

Define a restricted resident-set independence system and automatically search for violations of hereditary/exchange axioms.

### S3-EXP-0006 — Submodularity counterexample search

Related:

```text
[[S3-ZK-0012]]
```

Goal:

For an exact tiny cost model, enumerate subsets and test diminishing returns. Preserve smallest violations and characterize which compiler interaction caused them.

## Experiment template

```text
ID=
STATUS=PLANNED/RUNNING/SUPPORTED/REJECTED/INCONCLUSIVE
RELATED_ZETTEL=
MODEL=
INPUTS=
CONTROL=
MEASUREMENT=
FALSIFIER=
RESULT=
COUNTEREXAMPLE=
NEXT=
```
