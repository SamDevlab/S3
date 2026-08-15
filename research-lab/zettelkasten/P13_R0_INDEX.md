# P13.R0 Zettelkasten Overlay Index

This file is additive. It does not rewrite the historical `INDEX.md`.

```text
BASE_HISTORICAL_INDEX_MAX=S3-ZK-0062
P13_R0_INITIAL_RANGE=S3-ZK-0063..S3-ZK-0069
P13_R0_EXTENSION_RANGE=S3-ZK-0070..S3-ZK-0075
P13_R0_CURRENT_RANGE=S3-ZK-0063..S3-ZK-0075
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
| [[S3-ZK-0070]] | PERMANENT | SUPPORTED | Safety and profitability are separate optimization gates. |
| [[S3-ZK-0071]] | PERMANENT | SUPPORTED_AS_RESEARCH_MODEL | A local compiler improvement can worsen downstream cost. |
| [[S3-ZK-0072]] | ARCHITECTURE | SUPPORTED_AS_RESEARCH_REQUIREMENT | Dependence uncertainty is a legality boundary. |
| [[S3-ZK-0073]] | PERMANENT | SUPPORTED | Profitability is target-architecture dependent. |
| [[S3-ZK-0074]] | BRIDGE | SUPPORTED_AS_RESEARCH_REQUIREMENT | Opportunity counts need unique realizable effects. |
| [[S3-ZK-0075]] | PERMANENT | SUPPORTED | Semantic value identity is not incidental object identity. |

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
                                      |
                                      v
                                S3-ZK-0075
                              semantic identity
```

## Cluster E — P14 runtime discipline

```text
S3-ZK-0029 Causal metric hierarchy
             |
             v
S3-ZK-0068 Structural count != runtime oracle
             |
             v
S3-ZK-0070 Safety != profitability
             |
             +--------------+
             |              |
             v              v
       S3-ZK-0071      S3-ZK-0073
       downstream      target architecture
       interaction     profitability
             \              /
              \            /
               v          v
             P14 broad runtime rebase
```

## Cluster F — Dependence and opportunity accounting

```text
S3-ZK-0065 Explicit analysis semantics
             |
             v
S3-ZK-0072 Dependence uncertainty is a legality boundary
             |
             v
      effect-reordering passes

S3-ZK-0057 / 0060 / 0061
     event != avoidable opportunity
             |
             v
S3-ZK-0074 Unique realizable effects
             |
             v
      P14 causal census
```

## Scope reconciliation

Historical `S3-ZK-0033` remains valid for the P4 JSMN residual corpus where no phis or edge copies existed. It must not be generalized to later loop/phi-heavy workloads. P12.10–P12.14.2 provide later evidence that phi/reconstruction semantics can be correctness-critical.

The P13.R0 source set was extended after the initial closure from five to seven technical sources. The original files remain historical; the V2 files are the current source-set summary.

## Read with

Current authoritative P13.R0 literature summary:

- `research-lab/sources/P13_R0_FOUNDATION_CORPUS_V2.md`
- `research-lab/P13_R0_LITERATURE_REBASE_V2.md`

Historical first closure:

- `research-lab/sources/P13_R0_FOUNDATION_CORPUS.md`
- `research-lab/P13_R0_LITERATURE_REBASE.md`
