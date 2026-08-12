# Experiment Registry

Every serious hypothesis should receive a durable experiment record before production promotion.

Permanent IDs:

```text
S3-EXP-0001
S3-EXP-0002
...
```

## Queue and status

### S3-EXP-0001 — Binary min-cut vs exact oracle

STATUS=PLANNED

File: `S3-EXP-0001-mincut-vs-oracle.md`

Related: `S3-ZK-0005`, `0007`.

Cross-check binary materialization min-cut against exhaustive deterministic tiny problems.

### S3-EXP-0002 — RA OFF vs RA ON causal control

STATUS=SUPPORTED_BY_P4 / TOP_LEVEL_QUESTION_RESOLVED

File: `S3-EXP-0002-ra-off-vs-on.md`

Related: `S3-ZK-0006`, `0009`, `0013`, `0028`, `0031`.

P4 provided production-scale causal evidence. The existing liveness-aware whole-function allocator was not established as a poor algorithmic primary cause; the native backend defaulted `register_allocation=false`, causing location flexibility to collapse into emitter frame canonicalization. Making the existing allocator the native default reduced direct frame loads `1549 -> 491` and stores `1520 -> 471`.

Do not repeat this as an unresolved top-level experiment unless a future allocator change invalidates the causal control.

### S3-EXP-0003 — Lagrangian shared-capacity decomposition

STATUS=PLANNED

File: `S3-EXP-0003-lagrangian-capacity.md`

Related: `S3-ZK-0005`, `0007`, `0015`.

Compare priced independent min-cut subproblems with exact tiny multi-value capacity optimization.

### S3-EXP-0004 — Residence-domain laws

STATUS=PLANNED

Related: `S3-ZK-0003`, `0004`, `0011`.

Exhaustively verify order/join/meet laws and transfer monotonicity.

### S3-EXP-0005 — S3 location-flexibility loss histogram

STATUS=PARTIALLY_RESOLVED_BY_P4 / CONTINUE_FOR_METADATA_BOUNDARIES

Related: `S3-ZK-0001`, `0006`, `0009`, `0013`, `0028`.

P4 identified a major early loss boundary: `X8664Backend.register_allocation default false`. Continue this experiment only where needed to trace the residual metadata/SSA state that P4 did not remove.

### S3-EXP-0006 — Matroid exchange counterexample search

STATUS=PLANNED

Related: `S3-ZK-0008`.

Search restricted residence systems for hereditary/exchange violations.

### S3-EXP-0007 — Submodularity counterexample search

STATUS=PLANNED

Related: `S3-ZK-0012`.

Enumerate subsets and test submodular inequalities/diminishing returns.

### S3-EXP-0008 — Forward availability + backward memory necessity

STATUS=PLANNED_RESEARCH

Related: `S3-ZK-0002`, `0003`, `0014`.

Derive materialization frontiers and compare them with the exact placement oracle. P4 did not establish this model as necessary for production; keep it research-only until residual evidence supports it.

### S3-EXP-0009 — Current S3 ternary semantics/lowering map

STATUS=PLANNED

File: `S3-EXP-0009-ternary-semantics-map.md`

Related: `S3-ZK-0016`, `0017`, `0023`.

Establish exact S3 trit truth tables/operations and find the first physical-encoding layer.

### S3-EXP-0010 — Ternary operation-basis synthesis oracle

STATUS=PLANNED

File: `S3-EXP-0010-ternary-basis-oracle.md`

Related: `S3-ZK-0007`, `0018`, `0023`.

Exhaustively search small primitive bases over exact S3 trit semantics and compare target-lowering costs.

### S3-EXP-0011 — Semantic state minimization

STATUS=PLANNED

File: `S3-EXP-0011-ternary-state-minimization.md`

Related: `S3-ZK-0019`, `0020`, `0023`.

Test whether finite/ternary control states can be minimized before x86 branch lowering while preserving effects/failure behavior.

### S3-EXP-0012 — Ternary representation conversion graph

STATUS=PLANNED

File: `S3-EXP-0012-ternary-representation-graph.md`

Related: `S3-ZK-0017`, `0024`, `0007`.

Compare deterministic greedy representation choice with exact shortest-path/DP solutions on bounded trit computations.

### S3-EXP-0013 — Compiler information-loss boundary audit

STATUS=SUPPORTED_FOR_INITIAL_CORPUS / CROSS_WORKLOAD_OPEN

File: `S3-EXP-0013-information-loss-boundaries.md`

Related: `S3-ZK-0009`, `0021`, `0022`, `0027`, `0028`, `0030`.

Across a real value/state corpus classify logical identity, type/trit semantics, equivalence, location flexibility, representation flexibility, range, provenance, memory validity, initialization state, liveness and rematerializability as `PRESERVED`, `DERIVABLE`, `LOST`, `INTENTIONALLY_DISCARDED` or `UNKNOWN` at compiler boundaries.

P4 means the audit must include **configuration/pass enablement** as a boundary category, not only IR transformations. P5-AUDIT found that the exact P4 JSMN candidate preserves the physical identity of all 5638 byte-frame lines, but semantic necessity and dynamic weighting remain open.

### S3-EXP-0014 — Memory-state metadata provenance

STATUS=SUPPORTED_FOR_P4_JSMN_STATIC_ORIGIN / DYNAMIC_CLASSIFICATION_PARTIAL

File: `S3-EXP-0014-memory-state-metadata-provenance.md`

Related: `S3-ZK-0004`, `0021`, `0022`, `0027`, `0030`.

P4 measured metadata accesses unchanged at `5638 -> 5638`. P5-AUDIT reproduced the count and decomposed it into `4589` register-initialization accesses, `837` memory-initialization accesses and `212` trit payload accesses included by the lexical metric. P5-PREWORK added dynamic observer-aware counters. Physical origin is complete, but only 324 static and 356 JSMN dynamic checks have directly proven semantic outcomes; the remainder is UNKNOWN/UNMEASURED.

### S3-EXP-0015 — SSA destruction vs memory-state metadata staging

STATUS=SUPPORTED_NEGATIVE_FOR_P4_JSMN_CORPUS / PHI_HEAVY_REFINED

File: `S3-EXP-0015-ssa-destruction-metadata-staging.md`

Related: `S3-ZK-0006`, `0009`, `0027`, `0030`, `0031`.

Quantitatively separate ordinary value traffic, phi/loop staging, SSA-destruction metadata, initialization/memory-validity metadata, true RA spills and call/ABI traffic before selecting P5. P5-AUDIT found `0` emitted phi accesses and `0` critical edges in the P4 JSMN corpus. P5-PREWORK measured 712 internal O1 JSMN phis and 33 in a phi-heavy corpus; SSA is relevant when state reaches materialization, but the residual cannot be attributed to SSA alone.

### S3-EXP-0016 — Dynamic observer-aware initialization necessity

STATUS=SUPPORTED_FOR_OBSERVABILITY / NECESSITY_OPEN

File: `S3-EXP-0016-dynamic-observer-aware-initialization.md`

Related: S3-ZK-0035, 0036, 0037, 0038.

Temporary native instrumentation measured register/memory initialization and
trit payload reads/writes, observer class and dynamic site hotness across JSMN,
call-heavy, reference/address, slice, numeric and phi-heavy workloads. The
instrumentation is reverted. Exact JSMN dynamic weighting is reproducible, but
the remaining reset/store and observer populations are UNKNOWN/UNMEASURED.
Hosted emulator TADDR support is required before full reference/slice
differential closure.

## Current promotion order

```text
S3-EXP-0014 memory-state metadata provenance
        +
S3-EXP-0015 SSA destruction vs metadata staging
        +
S3-EXP-0016 dynamic observer-aware initialization necessity
        +
S3-EXP-0013 compiler-boundary information-loss audit
        ↓
P5 target selection
```

Parallel research remains:

```text
S3-EXP-0009..0012 ternary virtualization
S3-EXP-0001/0003/0004/0006/0007/0008 mathematical placement models
```

Do not let a speculative model displace the measured post-P4 bottleneck without causal evidence.

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
