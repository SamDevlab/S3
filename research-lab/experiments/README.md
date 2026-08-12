# Experiment Registry

Every serious hypothesis should receive a durable experiment record before production promotion.

IDs are permanent:

```text
S3-EXP-0001
S3-EXP-0002
...
```

## Initial queue

### S3-EXP-0001 — Binary min-cut vs exact oracle

File:

```text
S3-EXP-0001-mincut-vs-oracle.md
```

Related:

```text
[[S3-ZK-0005]]
[[S3-ZK-0007]]
```

Cross-check the binary materialization min-cut solution against exhaustive enumeration over deterministic tiny problems.

### S3-EXP-0002 — RA OFF vs RA ON causal control

File:

```text
S3-EXP-0002-ra-off-vs-on.md
```

Related:

```text
[[S3-ZK-0006]]
[[S3-ZK-0009]]
[[S3-ZK-0013]]
```

Measure how much frame/runtime behavior changes when the existing whole-function allocator is actually enabled under otherwise identical conditions.

### S3-EXP-0003 — Lagrangian shared-capacity decomposition

File:

```text
S3-EXP-0003-lagrangian-capacity.md
```

Related:

```text
[[S3-ZK-0005]]
[[S3-ZK-0007]]
[[S3-ZK-0015]]
```

Compare priced independent min-cut subproblems with the exact tiny multi-value capacity oracle.

### S3-EXP-0004 — Residence-domain laws

Related:

```text
[[S3-ZK-0003]]
[[S3-ZK-0004]]
[[S3-ZK-0011]]
```

Exhaustively verify order/join/meet laws and transfer monotonicity for candidate finite residence domains.

### S3-EXP-0005 — S3 location-flexibility loss histogram

Related:

```text
[[S3-ZK-0001]]
[[S3-ZK-0006]]
[[S3-ZK-0009]]
[[S3-ZK-0013]]
```

Trace real S3 values through as much of:

```text
SSA -> SSA destruction -> Assembly IR -> frame planning -> RA -> emitter
```

as factual instrumentation permits and record the earliest known point each value becomes memory-only.

### S3-EXP-0006 — Matroid exchange counterexample search

Related:

```text
[[S3-ZK-0008]]
```

Define a restricted resident-set independence system and search for hereditary/exchange violations.

### S3-EXP-0007 — Submodularity counterexample search

Related:

```text
[[S3-ZK-0012]]
```

For an exact tiny cost model, enumerate subsets and test submodular inequalities/diminishing returns.

### S3-EXP-0008 — Forward availability + backward memory necessity

Related:

```text
[[S3-ZK-0002]]
[[S3-ZK-0003]]
[[S3-ZK-0014]]
```

On tiny diamonds and loops, derive materialization frontiers from separate forward availability and backward necessity analyses, then compare them against the exact placement oracle.

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

## Rule

When an experiment produces a counterexample, create a `NEGATIVE_RESULT` Zettel before changing the model so the failed hypothesis remains durable knowledge.
