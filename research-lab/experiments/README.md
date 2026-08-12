# Experiment Registry

Every serious hypothesis should receive a durable experiment record before production promotion.

IDs are permanent:

```text
S3-EXP-0001
S3-EXP-0002
...
```

## Queue

### S3-EXP-0001 — Binary min-cut vs exact oracle

File: `S3-EXP-0001-mincut-vs-oracle.md`

Related: `S3-ZK-0005`, `0007`.

Cross-check binary materialization min-cut against exhaustive deterministic tiny problems.

### S3-EXP-0002 — RA OFF vs RA ON causal control

File: `S3-EXP-0002-ra-off-vs-on.md`

Related: `S3-ZK-0006`, `0009`, `0013`.

Measure frame/runtime behavior under identical workloads before blaming allocator quality.

### S3-EXP-0003 — Lagrangian shared-capacity decomposition

File: `S3-EXP-0003-lagrangian-capacity.md`

Related: `S3-ZK-0005`, `0007`, `0015`.

Compare priced independent min-cut subproblems with exact tiny multi-value capacity optimization.

### S3-EXP-0004 — Residence-domain laws

Related: `S3-ZK-0003`, `0004`, `0011`.

Exhaustively verify order/join/meet laws and transfer monotonicity.

### S3-EXP-0005 — S3 location-flexibility loss histogram

Related: `S3-ZK-0001`, `0006`, `0009`, `0013`.

Trace real values through SSA -> destruction -> Assembly IR -> frame planning -> RA -> emitter and record earliest known memory-only point.

### S3-EXP-0006 — Matroid exchange counterexample search

Related: `S3-ZK-0008`.

Search restricted residence systems for hereditary/exchange violations.

### S3-EXP-0007 — Submodularity counterexample search

Related: `S3-ZK-0012`.

Enumerate subsets and test submodular inequalities/diminishing returns.

### S3-EXP-0008 — Forward availability + backward memory necessity

Related: `S3-ZK-0002`, `0003`, `0014`.

Derive materialization frontiers and compare them with the exact placement oracle.

### S3-EXP-0009 — Current S3 ternary semantics/lowering map

File: `S3-EXP-0009-ternary-semantics-map.md`

Related: `S3-ZK-0016`, `0017`, `0023`.

Establish exact S3 trit truth tables/operations and find the first physical-encoding layer.

### S3-EXP-0010 — Ternary operation-basis synthesis oracle

File: `S3-EXP-0010-ternary-basis-oracle.md`

Related: `S3-ZK-0007`, `0018`, `0023`.

Exhaustively search small primitive bases over exact S3 trit semantics and compare target-lowering costs.

### S3-EXP-0011 — Semantic state minimization

File: `S3-EXP-0011-ternary-state-minimization.md`

Related: `S3-ZK-0019`, `0020`, `0023`.

Test whether finite/ternary control states can be minimized before x86 branch lowering while preserving effects/failure behavior.

### S3-EXP-0012 — Ternary representation conversion graph

File: `S3-EXP-0012-ternary-representation-graph.md`

Related: `S3-ZK-0017`, `0024`, `0007`.

Compare deterministic greedy representation choice with exact shortest-path/DP solutions on bounded trit computations.

### S3-EXP-0013 — Compiler information-loss boundary audit

File: `S3-EXP-0013-information-loss-boundaries.md`

Related: `S3-ZK-0009`, `0021`, `0022`, `0027`.

Across >=50 values classify logical identity/type/trit semantics/equivalence/location flexibility/representation flexibility/range/provenance/memory validity/liveness/rematerializability as PRESERVED, DERIVABLE, LOST, INTENTIONALLY_DISCARDED or UNKNOWN at each compiler boundary.

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
