# P4 Research Hypothesis — Global Value Residency & Memory Materialization

This document is intentionally broader than a production milestone specification. It defines the research question from which a later production P4 should be selected.

## Problem

P1–P3 removed real local/control/cross-block inefficiencies but did not materially reduce the representative aggregate load/store count. The remaining evidence points to broader frame canonicalization, with phi/SSA staging secondary and true RA spills not established as dominant.

## Primary hypothesis

S3 loses **location flexibility** too early.

A logical value that could still be represented by a virtual/register-side value acquires canonical frame identity before enough global information exists to decide whether memory is actually required.

## Architectural inversion under test

Current-ish mental model:

```text
logical value
    ↓
canonical frame identity
    ↓
optional late residence exceptions
```

Research model:

```text
logical value
    ↓
location-flexible identity
    ↓
constraints + liveness + alias/call/ABI facts
    ↓
choose among
    ├── keep flexible/register-eligible
    ├── materialize
    ├── recover
    └── rematerialize
```

## Research questions

1. At which exact phase is location flexibility first lost for hot values?
2. Which losses are semantically mandatory?
3. Can memory validity and register-side validity coexist safely for address-taken values?
4. Can materialization placement be optimized independently per value before register-capacity coupling?
5. Does restricted materialization placement reduce to min-cut?
6. What interaction first breaks that reduction?
7. Can a finite residence lattice/product domain express safe confluence at CFG joins?
8. Is an explicit `materialize` operation cleaner than implicit frame identity?
9. How much of phi traffic is memory-roundtrip implementation convenience?
10. After preserving cross-block virtual identity, do true RA spills finally become dominant?

## Mathematical toolbox

Candidate tools are not commitments:

```text
monotone data-flow equations
fixed-point iteration
lattices / complete lattices
reduced product abstract domains
Galois-style abstraction discipline
min cut
minimum-cost flow
primal-dual reasoning
exact bounded enumeration
integer/constraint oracle for tiny cases
matroid counterexample search
submodularity counterexample search
dominators / regions / loop weighting
```

## Mandatory evidence before production design

```text
FIRST_MEMORY_IDENTITY_LAYER_HISTOGRAM
HOT_VALUE_CORPUS >= 50 logical values
FRAME_TRAFFIC_CAUSE_BREAKDOWN
RA_OFF_VS_RA_ON comparison
PHI_STAGING attribution
LOOP_WEIGHTED traffic attribution
EXACT_ORACLE on tiny cases
MINCUT_VS_ORACLE comparison
MODEL_SCORECARD
```

## Candidate production outcomes

Research may lead to one of several different P4 implementations:

### A — Explicit location-flexible Assembly IR values

Use if Assembly IR/value representation is the earliest destructive layer.

### B — Lazy materialization / materialization-placement pass

Use if values retain identity but are eagerly made memory-valid without need.

### C — Register-preserving phi/SSA destruction

Use if phi/loop-carried edge staging dominates after ordinary canonicalization is accounted for.

### D — Real RA improvement

Use only if values reach RA correctly and measured allocator-created spills dominate.

### E — New architecture discovered by experiments

Allowed if it is safer/simpler/more effective than A–D and the evidence is preserved in the Zettelkasten.

## Non-goals

Do not use this research as an excuse for:

```text
unrelated optimizer rewrite
GPU backend
unsafe references
benchmark-specific fast paths
full LLVM-like infrastructure without measured need
```

## Promotion rule

The production P4 should be named after the **winning measured transformation**, not after this broad research umbrella.
