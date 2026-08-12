# P4 Research Hypothesis — Global Value Residency & Memory Materialization

STATUS: **PRODUCTION QUESTION PARTIALLY RESOLVED BY P4 / BROADER RESEARCH REMAINS OPEN**

Production reconciliation:

```text
research-lab/reconciliations/P4_20260812.md
```

Production PR:

```text
#170 — perf(p4): make global value residency the native default
```

## Original problem

P1–P3 removed real local/control/cross-block inefficiencies but did not materially reduce representative aggregate memory traffic. The broad research hypothesis was that S3 lost **location flexibility** too early.

## What P4 actually proved

P4 found a simpler and earlier causal boundary than the more exotic candidate models:

```text
X8664Backend.register_allocation default false
    ↓
default native backend selected RA_OFF
    ↓
emitter frame canonicalization
```

The existing allocator already consumed whole-function CFG liveness and provided deterministic global value residency. P4 therefore selected:

```text
SELECTED_MODEL=
existing liveness-backed global value residency with explicit stack-backed opt-out

SELECTED_TRANSFORMATION=
make register allocation the native default while preserving register_allocation=false fallback
```

No allocator redesign, Assembly IR redesign, phi rewrite, min-cut materialization pass or new global residence lattice was needed for the production P4 capability.

Direct evidence:

```text
frame loads:  1549 -> 491
frame stores: 1520 -> 471
coverage: 13/13 targeted opportunities
```

This supports the core thesis that an avoidable location-flexibility collapse existed, but the specific production cause was **configuration/default policy**, not absence of global liveness/allocation machinery.

## What P4 did NOT prove

P4 does not prove that:

- min-cut is the correct general materialization algorithm;
- a residence lattice should become production IR state;
- explicit `materialize` IR is required;
- current allocator quality is optimal;
- phi/SSA staging is dominant;
- all remaining frame/memory traffic is avoidable.

These remain research questions.

## Important residual split

P4 measured:

```text
TOTAL_FRAME_ACCESSES: 9282 -> 7175
METADATA_ACCESSES:     5638 -> 5638
```

Therefore ordinary value residency and memory/initialized-state metadata must now be treated as separate causal state spaces.

Residual production diagnosis:

```text
REPEATED_MEMORY_STATE_MATERIALIZATION
```

Recommended next research area:

```text
SSA_DESTRUCTION_AND_MEMORY_STATE_METADATA_STAGING
```

## Revised research questions

1. What exactly constitutes the unchanged metadata access population?
2. Which metadata accesses are semantically/ABI mandatory?
3. Which are initialization-state, memory-validity, phi/loop or late emitter staging?
4. What is the earliest introduction layer for repeated metadata materialization?
5. Does SSA destruction contribute a dominant share after P4?
6. Are loop-carried phi values dynamically dominant?
7. Do true RA spills become significant only after metadata/SSA traffic is removed?
8. Can reduced-product or bounded fact domains preserve memory-validity/initialization facts without repeated physical realization?
9. Do min-cut/lazy-materialization models become relevant to the residual state problem, or were they solving the wrong level?
10. Can exact bounded oracles quantify remaining materialization optimality gaps?

## Mathematical toolbox retained as research

```text
monotone data-flow equations
fixed-point iteration
lattices / reduced products
abstract interpretation
min cut / minimum-cost flow
primal-dual/Lagrangian reasoning
exact bounded enumeration
matroid/submodularity counterexample search
dominators / regions / loop weighting
term rewriting / bounded decision procedures
```

These are tools, not commitments.

## Next mandatory evidence before P5 selection

```text
S3-EXP-0014 memory-state metadata provenance
S3-EXP-0015 SSA destruction vs metadata staging
S3-EXP-0013 information-loss boundary audit
```

Quantitatively separate:

```text
ordinary value traffic
phi edge copies
loop-phi staging
SSA-destruction metadata
initialization/memory-validity metadata
true RA spills
call/ABI traffic
mandatory reference/address identity
unknown
```

## Promotion rule

Do not call the next production milestone “SSA optimization” or “RA optimization” merely because those are plausible categories.

Name P5 only after the dominant residual cause and its earliest introduction layer are measured.
