# S3 Research Lab — Zettelkasten + Compiler Optimization

This directory is a **long-lived research workspace** for S3 compiler research.
It is intentionally isolated on the branch `research/zettelkasten-lab-20260812`.

## Why this exists

The production optimization campaign P1–P3 showed that local and limited cross-block emitter improvements are real but insufficient to move the large global frame/load-store counters. The research problem is now broader: preserve useful logical-value information long enough for later compiler phases to make better representation and placement decisions.

This lab keeps that research durable across:

- ChatGPT/Codex conversation migrations and context limits;
- experimental dead ends;
- competing mathematical models;
- prototypes that are not production quality;
- literature-derived ideas and original S3 hypotheses.

## Isolation contract

**Do not merge this research branch directly into `main`.**

When an idea is promoted:

1. reproduce/validate it here;
2. record evidence and counterexamples in the Zettelkasten;
3. define one narrow production milestone;
4. create a fresh production branch from current `origin/main`;
5. port only the proven production-quality mechanism;
6. run normal S3 correctness/native/full-suite/CI gates there.

The research branch may contain prototypes, exact-but-exponential oracles, rejected experiments, and analysis tooling.

## Durable entry points

```text
research-lab/
├── README.md
├── HANDOFF.md
├── STATE.json
├── NEW_CHAT_PROMPT.md
├── RESEARCH_PROTOCOL.md
├── ROADMAP.md
├── DECISIONS.md
├── SESSION_LOG.md
├── sources/
│   └── README.md
├── zettelkasten/
│   ├── README.md
│   ├── INDEX.md
│   ├── TEMPLATE.md
│   └── notes/S3-ZK-*.md
├── hypotheses/
│   └── P4_GLOBAL_VALUE_RESIDENCY.md
├── experiments/
│   ├── README.md
│   └── S3-EXP-*.md
└── prototypes/
    ├── README.md
    ├── cfg.py
    ├── liveness.py
    ├── residence_lattice.py
    ├── materialization_cut.py
    ├── exact_oracle.py
    ├── combinatorial_checks.py
    ├── lagrangian_capacity.py
    ├── multivalue_oracle.py
    ├── s3_adapter.py
    ├── value_trace.py
    ├── trace_cli.py
    ├── demo.py
    └── capacity_demo.py
```

GitHub issue `#171` is the durable external locator for this lab.

## Core research question

> At what earliest compiler phase does an S3 logical value unnecessarily lose location flexibility and acquire memory/frame identity?

Primary architecture hypothesis:

```text
OLD MENTAL MODEL
logical value -> frame identity -> occasionally kept in a register

RESEARCH MODEL
logical value -> location-flexible
              -> analyze constraints/liveness/cost
              -> register | memory | rematerialize
                 materialize only when required
```

## Mathematical directions under active investigation

```text
monotone fixed-point data flow
residence lattices / reduced products
forward availability + backward necessity
lazy materialization
min-cut / minimum-cost placement
exact bounded optimization oracles
Lagrangian relaxation of shared register capacity
matroid exchange structure (prove or reject)
submodularity (prove or reject)
location-flexibility information-loss metrics
```

## Research values

- Semantics and safety are hard constraints.
- Benchmark numbers are characterization, not correctness gates.
- A beautiful model that does not improve measured compiler behavior is a rejected experiment, not a success.
- Negative results are first-class knowledge.
- Exact/expensive algorithms are welcome as **oracles** even when unsuitable for production.
- Preserve information as long as possible; collapse representation choices only when a later constraint requires it.
- Measure the earliest causal layer, not only the final emitted `mov`.
- Do not call frame traffic a true RA spill unless the allocation decision actually caused it.

## Current production anchor

At lab creation:

```text
S3_MAIN=a83e25c3364302227694399ebe12946f887c0ead
P3_PR=169
P3_IMPLEMENTATION_HEAD=4643f60176aec68c7a4d7203f3623bde8bac2ae4
P3_MERGE_COMMIT=a83e25c3364302227694399ebe12946f887c0ead
P3_STATUS=COMPLETE
P4_STARTED=NO
```

Important later code-inspection fact stored in `S3-ZK-0013`: at this anchor the existing allocator already consumes whole-function CFG liveness and greedily colors virtual registers. Therefore `RA OFF` vs `RA ON` is a mandatory causal control before concluding allocator quality is the dominant remaining problem.

See `HANDOFF.md`, `STATE.json`, `NEW_CHAT_PROMPT.md`, and `zettelkasten/INDEX.md` before continuing research in a new session.
