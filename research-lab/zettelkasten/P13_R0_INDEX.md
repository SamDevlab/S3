# P13.R0 Zettelkasten Overlay Index

This file is additive. It does not rewrite the historical `INDEX.md`.

```text
BASE_HISTORICAL_INDEX_MAX=S3-ZK-0062
P13_R0_RANGE=S3-ZK-0063..S3-ZK-0069
DATE=2026-08-15
```

| ID | Type | Status | Atomic idea |
|---|---|---|---|
| [[S3-ZK-0063]] | PERMANENT | SUPPORTED | Partial phi knowledge is not constant proof. |
| [[S3-ZK-0064]] | PERMANENT | SUPPORTED | Loop phis are loop-carried state, not ignorable merge syntax. |
| [[S3-ZK-0065]] | ARCHITECTURE | SUPPORTED_AS_RESEARCH_REQUIREMENT | Analysis facts need explicit abstract semantics. |
| [[S3-ZK-0066]] | PERMANENT | SUPPORTED | Definite initialization is a forward must proof. |
| [[S3-ZK-0067]] | PERMANENT | SUPPORTED | Pass order and IR level are causal variables. |
| [[S3-ZK-0068]] | PERMANENT | SUPPORTED | Structural instruction count is not a runtime oracle. |
| [[S3-ZK-0069]] | ARCHITECTURE | SUPPORTED | SSA reconstruction is a correctness boundary. |

## Cluster D — P13 compiler correctness foundation

```text
                       S3-ZK-0065
              Explicit abstract semantics
                 /        |        \
                v         v         v
        S3-ZK-0063   S3-ZK-0066   S3-ZK-0067
        SCCP phi      init must     pass/IR stage
            |                         |
            v                         v
        S3-ZK-0064 ------------> S3-ZK-0069
        loop phi                  SSA reconstruction
```

## Cluster E — P14 runtime discipline

```text
S3-ZK-0029 Causal metric hierarchy
             |
             v
S3-ZK-0068 Structural count != runtime oracle
             |
             v
P14 broad runtime rebase
```

## Scope reconciliation

Historical `S3-ZK-0033` remains valid for the P4 JSMN residual corpus where no phis or edge copies existed. It must not be generalized to later loop/phi-heavy workloads. P12.10–P12.14.2 provide later evidence that phi/reconstruction semantics can be correctness-critical.

## Read with

- `research-lab/sources/P13_R0_FOUNDATION_CORPUS.md`
- `research-lab/P13_R0_LITERATURE_REBASE.md`
