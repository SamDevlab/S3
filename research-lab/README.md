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

## Operational truth and production provenance

`STATE.json` is the canonical machine-readable research status. `HANDOFF.md` is the current narrative handoff. `SESSION_LOG.md`, reconciliations, and old roadmap phases are durable historical evidence and must not override current Git state or `STATE.json`.

The copy of `bootstrap/` that lives on this long-lived research branch is **not automatically the current production compiler**. It may intentionally lag `main`. Therefore:

- never use the research-branch `bootstrap.s3` import as evidence about current production unless its exact commit is the declared target;
- any experiment that measures current production must declare `TARGET_MAIN_SHA`;
- production-coupled experiments must run against a separate worktree/checkout whose `HEAD` equals that SHA;
- record both `RESEARCH_HEAD` and `TARGET_MAIN_SHA` in persistent experiment evidence;
- if the target checkout moves, invalidate or rerun measurements that depended on the old SHA.

Before a production-coupled experiment, run:

```bash
python research-lab/tools/validate_lab.py \
  --production-checkout /path/to/s3-main-worktree \
  --production-sha <TARGET_MAIN_SHA>
```

For a structural lab-only check:

```bash
python research-lab/tools/validate_lab.py
```

## Workflow provenance containment

Automation policy is part of the state of the exact ref being published.
Before a future remote write, use the local bounded simulator against the
proposed commit, target branch, and diff base:

```bash
python research-lab/tools/validate_remote_write.py \
  --target-ref research/zettelkasten-lab-20260812 \
  --target-head-before <REMOTE_HEAD> \
  --proposed-head <LOCAL_PROPOSED_HEAD> \
  --event push
```

The tool returns exit 0 only for `PROVEN_ZERO_ACTIONS`. Unsupported YAML,
unknown trigger shapes, pull-request merge semantics, and parsing failures
return `UNKNOWN` and a non-zero exit. A `PROVEN_ZERO_ACTIONS` result answers
only the trigger question; it does not authorize a remote write.

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
├── tools/
│   ├── validate_lab.py
│   ├── validate_remote_write.py
│   └── test_validate_remote_write.py
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
- Measurements are identified by the exact compiler SHA that produced them.

## Historical production anchor at lab creation

The following block is historical context, not current production state:

```text
S3_MAIN=a83e25c3364302227694399ebe12946f887c0ead
P3_PR=169
P3_IMPLEMENTATION_HEAD=4643f60176aec68c7a4d7203f3623bde8bac2ae4
P3_MERGE_COMMIT=a83e25c3364302227694399ebe12946f887c0ead
P3_STATUS=COMPLETE
P4_STARTED=NO
```

Important later code-inspection fact stored in `S3-ZK-0013`: at this anchor the existing allocator already consumes whole-function CFG liveness and greedily colors virtual registers. Therefore `RA OFF` vs `RA ON` is a mandatory causal control before concluding allocator quality is the dominant remaining problem.

For current state, read `STATE.json`, then reconcile it with the actual Git refs. See `HANDOFF.md`, `NEW_CHAT_PROMPT.md`, and `zettelkasten/INDEX.md` for narrative context.
