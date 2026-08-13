# S3 Research Lab Roadmap

## Status of this document

This file preserves the original P4-era research roadmap. It is historical planning evidence, not the authoritative current queue.

Do not interpret labels such as `NEXT`, `P4 selection`, or the R0-R6 ordering below as current program status. For current state use, in order:

1. actual Git refs and observed execution facts;
2. `STATE.json`;
3. `HANDOFF.md`;
4. current Zettelkasten, experiment records, and reconciliations.

When current work advances beyond this historical plan, preserve the old plan rather than rewriting history. New active research direction belongs in `STATE.json`, `HANDOFF.md`, experiment records, and dated reconciliations.

---

## Historical roadmap - P4 research campaign

This is a research roadmap, not the production milestone roadmap.

## R0 - Durable research substrate - DONE

- long-lived isolated branch;
- handoff document;
- machine-readable state;
- Zettelkasten conventions/index;
- source catalog;
- experiment registry;
- generic mathematical prototypes.

## R1 - Mathematical sanity - HISTORICAL PLAN

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

## R2 - Real S3 trace bridge - HISTORICAL PLAN

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

## R3 - Frame traffic attribution - HISTORICAL PLAN

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

## R4 - Competing architecture prototypes - HISTORICAL PLAN

At least compare:

```text
A. eager canonicalization baseline
B. lazy materialization
C. explicit cross-block virtual identity
D. phi edge-copy / parallel-copy path if warranted
E. selected novel mathematical model
```

Use exact oracle where small enough.

## R5 - Production P4 selection - HISTORICAL, COMPLETED LATER

Historical intent:

Select one winning coherent capability from evidence.

Only here define the production P4 name/scope.

Create a fresh production branch from current main; do not merge this research branch.

The later research record shows that P4 was selected, promoted and followed by subsequent production campaigns. Consult `STATE.json` and dated reconciliations for factual current status.

## R6 - Post-P4 knowledge update - HISTORICAL, COMPLETED/CONTINUED LATER

Historical intent after production P4 merged:

- update `STATE.json`;
- update `HANDOFF.md`;
- promote/reject relevant Zettels;
- record post-merge bottleneck;
- decide whether RA, phi/SSA, loops, calls, instruction selection, or another layer is next.

This activity became an ongoing research practice rather than a one-time roadmap phase.
