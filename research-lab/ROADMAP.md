# S3 Research Lab Roadmap

This is a research roadmap, not the production milestone roadmap.

## R0 — Durable research substrate — DONE

- long-lived isolated branch;
- handoff document;
- machine-readable state;
- Zettelkasten conventions/index;
- source catalog;
- experiment registry;
- generic mathematical prototypes.

## R1 — Mathematical sanity — NEXT

Goals:

- validate residence-domain laws;
- cross-check min-cut vs exact oracle at larger deterministic sample counts;
- find the boundary where shared register capacity breaks per-value cut independence;
- construct matroid and submodularity counterexamples/positive restricted cases.

Deliverables:

```text
S3-EXP-0001..0003
new ZK notes / negative results
```

## R2 — Real S3 trace bridge

Goals:

- adapt real AssemblyFunctions to generic CFG;
- cross-check generic liveness against production liveness;
- build >=50-value corpus;
- measure first known memory-only layer at Assembly/RA boundary;
- extend tracing earlier toward SSA destruction/Assembly IR construction.

Key metric:

```text
FIRST_LOCATION_FLEXIBILITY_LOSS_HISTOGRAM
```

## R3 — Frame traffic attribution

Goals:

Separate:

```text
mandatory address/reference
ABI/call preservation
phi/SSA staging
pre-RA canonicalization
true RA spills
emitter staging
unknown
```

Weight hot loops separately from cold static traffic.

## R4 — Competing architecture prototypes

At least compare:

```text
A. eager canonicalization baseline
B. lazy materialization
C. explicit cross-block virtual identity
D. phi edge-copy / parallel-copy path if warranted
E. selected novel mathematical model
```

Use exact oracle where small enough.

## R5 — Production P4 selection

Select **one** winning coherent capability from evidence.

Only here define the production P4 name/scope.

Create a fresh production branch from current main; do not merge this research branch.

## R6 — Post-P4 knowledge update

After production P4 merges:

- update `STATE.json`;
- update `HANDOFF.md`;
- promote/reject relevant Zettels;
- record post-merge bottleneck;
- decide whether RA, phi/SSA, loops, calls, instruction selection, or another layer is next.
