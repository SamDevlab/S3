# Research Session Log

## 2026-08-12 — Lab initialization

Production anchor:

```text
origin/main=a83e25c3364302227694399ebe12946f887c0ead
P3=COMPLETE
P4=NOT_STARTED
```

Actions:

- created long-lived branch `research/zettelkasten-lab-20260812` from P3 main;
- created durable handoff/state/new-chat bootstrap;
- established Zettelkasten protocol and seed notes `S3-ZK-0001..0012`;
- cataloged the initial literature corpus without copying source PDFs;
- created broad P4 research hypothesis rather than prematurely naming a production implementation;
- created experiment registry;
- created research prototypes for:
  - generic CFG;
  - backward fixed-point liveness;
  - finite residence powerset lattice;
  - binary materialization min-cut;
  - exhaustive exact placement oracle;
  - matroid exchange counterexample search;
  - submodularity counterexample search;
  - S3 Assembly -> generic CFG adapter;
  - Assembly-level value trace scaffold;
- created GitHub issue #171 as a durable locator.

Current unresolved priority:

```text
prove/reject the restricted min-cut model;
measure real S3 location-flexibility loss;
attribute memory traffic before selecting production P4.
```

No production code was changed on `main`.
No production PR was opened.
