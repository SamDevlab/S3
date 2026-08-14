# P9.2 Explicit Range-Fact Contract Reconciliation

## Checkpoint

```text
P9_2_STATUS=COMPLETE_RESEARCH_ONLY
P9_2_TARGET_KIND=CORRECTNESS_CANDIDATE_NOT_MAIN
P9_2_TARGET_SHA=045bbb1427af941b71d28b93cf1e5fe9bf245af7
TARGET_IS_MAIN=NO
TARGET_HEAD_MATCH=YES
```

Correction A and Correction B were validated as a stacked correctness
candidate. The candidate is not called post-correctness main because neither
correction was integrated into `origin/main`.

## Baseline Reconciliation

The exact old production target `5dd6844607ba3a2d5830ed836fb9026eed86d0fb`
reproduced the published P9 model:

```text
OLD_P9_MODEL_EXPECTED=289500
OLD_P9_MODEL_REPRODUCED=YES
OLD_P9_MODEL_ACTUAL=289500
WORKLOADS=15
```

The same model on A+B produced:

```text
CORRECTNESS_CANDIDATE_MODEL=289512
CORRECTNESS_ONLY_DELTA=12
```

The delta is attributed only to correctness changes. It is not a performance
claim or a P9 opportunity.

## P9.2 Evidence

```text
CLASSIFICATION_COVERAGE=1.0
REQUIRED_DYNAMIC=65224
AVOIDABLE_DYNAMIC=0
UNKNOWN_DYNAMIC=26456
BOUNDS_DYNAMIC=17464
VALIDITY_DYNAMIC=6660
PROVABLY_REDUNDANT_SITES=0
PROVABLY_REDUNDANT_DYNAMIC=0
WORKLOADS_WITH_AVOIDABLE_SITES=0
CHECKED_FALLBACK_SITES=9060
```

The full machine-readable result is `P9_2_RESULT.json`. All twenty negative
controls are `CHECK_RETAINED`, including redefinitions, non-dominating checks,
joins, loop entries, calls, aliases, conversions, overflow, negative indexes,
`index == length`, immutability, failure ordering and low instruction limits.

## Model Decision

```text
MODEL_A_RECOMPUTE=PASS_NO_SAFE_AVOIDABLE_SUBCLASS
MODEL_B_PRIVATE_FACT=NOT_NEEDED
MODEL_C_PUBLIC_CONTRACT=REJECTED_NOT_JUSTIFIED
SAFE_AVOIDABLE_SUBCLASS=NO
MATERIALITY=NO_SAFE_AVOIDABLE_DYNAMIC
P9_2_SELECTION=NO_VALID_TARGET_YET
P9_PRODUCTION_STARTED=NO
```

Model A recomputation over validated Assembly/CFG was the smallest sufficient
model. A structural private fact keyed by `InstructionSite` remains a possible
future mechanism, but there was no fact to transport. A public Assembly
contract was not justified and was not changed.

The first fact-loss boundary is
`ASSEMBLY_TO_EMITTER_RANGE_FACT_CONTRACT_NOT_EXPLICIT`. It identifies an open
research boundary, not a production authorization.

## Safety And Provenance

```text
LAB_CONSISTENCY=PASS
TARGET_HEAD_MATCH=YES
PRODUCTION_CODE_CHANGED=NO
BENCHMARK_EXECUTED=NO
GITHUB_ACTIONS_EXECUTED=NO
SHUTDOWN_AUTHORIZED=NO
```

The temporary candidate analysis used an exact detached checkout. The durable
research branch remains separate from production. No research push is recorded
until the remote-write validator returns `PROVEN_ZERO_ACTIONS` for the exact
proposed ref.
