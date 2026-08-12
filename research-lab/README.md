# S3 Research Lab — Zettelkasten + Compiler Optimization

This directory is a **long-lived research workspace** for S3 compiler research.
It is intentionally isolated on the branch `research/zettelkasten-lab-20260812`.

## Why this exists

The production optimization campaign P1–P3 showed that local and limited cross-block emitter improvements are real but insufficient to move the large global frame/load-store counters. The research problem is now broader: preserve useful logical-value information long enough for later compiler phases to make better representation and placement decisions.

This lab exists to keep that research durable across:

- ChatGPT conversation migrations/context limits;
- experimental dead ends;
- competing mathematical models;
- prototype implementations that are not yet production quality;
- literature-derived ideas and original S3 hypotheses.

## Isolation contract

**Do not merge this research branch directly into `main`.**

When an idea is promoted:

1. reproduce/validate it here;
2. record the evidence in the Zettelkasten;
3. define a narrow production milestone;
4. create a fresh production branch from current `origin/main`;
5. port only the proven production-quality change;
6. run normal S3 correctness/native/full-suite/CI gates there.

The research branch may contain prototypes, oracles, deliberately slow exact algorithms, rejected experiments, and analysis tooling.

## Directory map

```text
research-lab/
├── README.md
├── HANDOFF.md
├── STATE.json
├── RESEARCH_PROTOCOL.md
├── sources/
│   └── README.md
├── zettelkasten/
│   ├── README.md
│   ├── INDEX.md
│   ├── TEMPLATE.md
│   └── notes/
├── hypotheses/
│   └── P4_GLOBAL_VALUE_RESIDENCY.md
├── experiments/
│   └── README.md
└── prototypes/
    ├── README.md
    ├── cfg.py
    ├── liveness.py
    ├── residence_lattice.py
    ├── materialization_cut.py
    ├── exact_oracle.py
    └── demo.py
```

## Core research question

> At what earliest compiler phase does an S3 logical value unnecessarily lose location flexibility and acquire memory/frame identity?

The primary architecture hypothesis is an inversion of the current default:

```text
OLD MENTAL MODEL
logical value -> frame identity -> occasionally kept in a register

RESEARCH MODEL
logical value -> location-flexible -> register | memory | rematerialize
                                      only materialize when required
```

## Research values

- Semantics and safety are hard constraints.
- Benchmark numbers are characterization, not correctness gates.
- A beautiful mathematical model that does not improve measured compiler behavior is a rejected experiment, not a success.
- Negative results are first-class knowledge.
- Exact/expensive algorithms are welcome as **oracles** even when unsuitable for production.
- Preserve information as long as possible; collapse representation choices only when a later constraint requires it.
- Measure the earliest causal layer, not only the final emitted `mov`.

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

See `HANDOFF.md` and `STATE.json` before continuing research in a new session.
