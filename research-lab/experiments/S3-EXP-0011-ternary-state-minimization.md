# S3-EXP-0011 — Ternary/state-machine minimization before branch lowering

STATUS: PLANNED

RELATED_ZETTEL:

```text
S3-ZK-0019
S3-ZK-0020
S3-ZK-0023
```

## Question

Do real S3 control regions contain finite semantic states that can be proven equivalent and minimized before x86 binary branching?

## Inputs

Start with generated micro-CFGs, then parser/state-machine-like real workloads. Include side-effecting negative controls.

## Compare

```text
SEMANTIC_STATES_BEFORE/AFTER
CFG_BLOCKS_BEFORE/AFTER
BRANCHES_BEFORE/AFTER
STATE_UPDATES_BEFORE/AFTER
NATIVE_EQUIVALENCE
```

## Safety

State equivalence must include observable failure behavior, calls, stores, reference effects and return values. Pure control equivalence is insufficient when effects differ.
