# S3-EXP-0037 - P10.1 Frame Representation Causal Decomposition

```text
ID=S3-EXP-0037
STATUS=COMPLETE_NO_VALID_TARGET_YET
CAMPAIGN=P10_1_FRAME_REPRESENTATION_CAUSAL_DECOMPOSITION_V1
TARGET_KIND=VALIDATED_CORRECTNESS_CANDIDATE_NOT_MAIN
TARGET_SHA=045bbb1427af941b71d28b93cf1e5fe9bf245af7
RELATED_ZETTEL=S3-ZK-0062
```

## Question And Frozen Inputs

Can the broad P10 `FRAME_CANONICALIZATION=39081` population be causally
separated into true spill/reload, logically required frame traffic, ABI work,
address materialization, representation choice or a concrete avoidable pattern?

The exact P10 sidecar JSON on the frozen A+B candidate was consumed as a
research-only input. No production imports, compiler execution, benchmark,
candidate modification or allocation redesign was performed.

```text
TARGET_IS_MAIN=NO
TARGET_IS_VALIDATED_CORRECTNESS_CANDIDATE=YES
TARGET_HEAD_MATCH=YES
TARGET_MAIN_ANCESTRY=YES
BASELINE_EXPECTED=289512
BASELINE_REPRODUCED=YES
BASELINE_ACTUAL=289512
WORKLOADS=15
```

## Exact Broad-Class Decomposition

The sidecar exposes `frame_value_line_count` and
`stack_frame_value_line_count`. The broad class splits exactly into two
mutually exclusive measured subfamilies:

| Family | Static | Dynamic | Share of frame | Workloads | Avoidability |
| --- | ---: | ---: | ---: | ---: | --- |
| LOGICAL_FRAME_VALUE_TRAFFIC | 11524 | 14795 | 37.8573% | 15 | ATTRIBUTION_LIMIT_ONLY |
| OTHER_FRAME_REPRESENTATION | 18936 | 24286 | 62.1427% | 15 | ATTRIBUTION_LIMIT_ONLY |
| **Total** | **30460** | **39081** | **100%** | 15 | **1.0 coverage** |

The `10063` stack-resident frame-value events are an overlay inside the first
row, not a third additive class. They show physical stack residence but do
not establish why residence was selected.

## Spill And Pressure Decision

```text
LOGICAL_FRAME_VALUE_DYNAMIC=14795
PHYSICAL_STACK_VALUE_DYNAMIC=10063
TRUE_SPILL_STORE_DYNAMIC=0_PROVEN
TRUE_SPILL_RELOAD_DYNAMIC=0_PROVEN
NON_SPILL_STACK_DYNAMIC=UNKNOWN_NOT_ESTABLISHED
TRUE_SPILL_CAUSALITY_ESTABLISHED=NO
TRUE_RELOAD_CAUSALITY_ESTABLISHED=NO
```

The sidecar has no live-before/live-after sets, exact frame slots, call-clobber
survivor sets or allocatable-capacity observations for each emitted frame
line. Therefore:

```text
MAX_REGISTER_PRESSURE_OBSERVED=UNKNOWN_NOT_MEASURED
SITES_PRESSURE_EXCEEDS_CAPACITY=UNKNOWN_NOT_MEASURED
WORKLOADS_WITH_PRESSURE_EXCEEDANCE=UNKNOWN_NOT_MEASURED
PRESSURE_CAUSALITY_PROVEN=NO
```

Stack residency is not relabeled as spill. No exact or conservative allocation
oracle was constructed because the required live-interval, fixed-register,
call-clobber, address-taken and copy constraints were not available in the
sidecar. An approximate oracle would not prove avoidability.

## Other Required Separations

```text
ABI_SAVE_DYNAMIC=0_PROVEN
ABI_RESTORE_DYNAMIC=0_PROVEN
PARAMETER_HOME_DYNAMIC=NOT_SEPARATELY_MEASURED
RETURN_VALUE_DYNAMIC=NOT_SEPARATELY_MEASURED
FRAME_ADDRESS_CALC_DYNAMIC=NOT_SEPARATELY_MEASURED
STACK_SLOT_ACCESS_DYNAMIC=NOT_SEPARATELY_MEASURED
REGISTER_TO_FRAME_MATERIALIZATION_DYNAMIC=NOT_SEPARATELY_MEASURED
FRAME_TO_REGISTER_MATERIALIZATION_DYNAMIC=NOT_SEPARATELY_MEASURED
TMOV_COPY_MATERIALIZATION_STATIC=108
TMOV_COPY_MATERIALIZATION_DYNAMIC=240
```

The TMOV count is recorded only as historical correctness-related evidence;
Correction B's `ALWAYS_MATERIALIZE_TMOV` decision is not reopened. The broad
frame class contains no demonstrated ABI, address-only, load/store-only or
pressure-only subpopulation that can be safely promoted.

## Counterfactual And Selection Gate

```text
ORACLE_USED=NO
ORACLE_SCOPE=NONE
CURRENT_TRAFFIC=39081
ORACLE_MINIMUM_TRAFFIC=UNKNOWN_NOT_COMPUTED
ORACLE_GAP=UNKNOWN_NOT_COMPUTED
PROVABLY_REQUIRED_DYNAMIC=0
PROVABLY_AVOIDABLE_DYNAMIC=0
POTENTIALLY_AVOIDABLE_UNPROVEN_DYNAMIC=0
ATTRIBUTION_LIMIT_ONLY_DYNAMIC=39081
MAX_THEORETICAL_REMOVABLE_DYNAMIC=0
MAX_THEORETICAL_SHARE_OF_MODEL=0.0
MAX_THEORETICAL_SHARE_OF_FRAME_CLASS=0.0
CONCRETE_SPILL_EXAMPLE_FOUND=NO
CONCRETE_NON_SPILL_AVOIDABLE_EXAMPLE_FOUND=NO
```

No valid counterfactual allocation/layout/emission model was established.
Consequently no event is labeled `PROVABLY_AVOIDABLE` or
`POTENTIALLY_AVOIDABLE_UNPROVEN`; unresolved frame attribution is explicitly
`ATTRIBUTION_LIMIT_ONLY`.

```text
P10_1_SELECTION=NO_VALID_TARGET_YET
TARGET_SUBCLASS=NONE
TARGET_DYNAMIC=0
TARGET_WORKLOADS=0
FIRST_CAUSAL_BOUNDARY=FRAME_LAYOUT_OR_EMITTER_LOCAL_DECISION_NOT_SEPARATED
FRAME_LINE_STATUS=CLOSE
NEXT_EXPERIMENT=NONE_WITHIN_FRAME
NEXT_DISCRIMINATING_QUESTION=NONE_WITHOUT_CAUSAL_EXAMPLE
```

## Safety And Provenance

```text
PRODUCTION_OPTIMIZATION_STARTED=NO
CORRECTNESS_INTEGRATION_STATUS=STILL_BLOCKED_BY_PROVENANCE
CORRECTNESS_INTEGRATED=NO
GITHUB_ACTIONS_EXECUTED=NO
BENCHMARK_EXECUTED=NO
SHUTDOWN_AUTHORIZED=NO
```

The frame line closes negatively. A future campaign would need a separate
causal instrumentation or exact bounded allocation study before any target
could be selected.
