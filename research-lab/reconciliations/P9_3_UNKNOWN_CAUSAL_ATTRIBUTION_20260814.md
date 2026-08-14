# P9.3 UNKNOWN Causal Attribution Reconciliation

## Status

```text
P9_3_CAMPAIGN=P9_3_UNKNOWN_CAUSAL_ATTRIBUTION_V1
P9_3_STATUS=COMPLETE_RESEARCH_ONLY
INITIAL_MAIN=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
CORRECTNESS_CANDIDATE_SHA=045bbb1427af941b71d28b93cf1e5fe9bf245af7
TARGET_IS_MAIN=NO
TARGET_IS_VALIDATED_CORRECTNESS_CANDIDATE=YES
TARGET_HEAD_MATCH=YES
P9_3_BASELINE_EXPECTED=289512
P9_3_BASELINE_REPRODUCED=YES
P9_3_BASELINE_ACTUAL=289512
```

The candidate remains the stacked, validated genealogy `MAIN -> A -> B`.
Correction A is structural instruction-site identity; Correction B is
`ALWAYS_MATERIALIZE_TMOV`. The candidate was not integrated into main.

## Exact UNKNOWN Partition

P9.1's complete 9060-record ledger was aggregated without adding a stronger
range analysis. Its `REGISTER_INITIALIZATION_CHECK` line counts are:

```text
TOTAL_UNKNOWN_DYNAMIC=26456
UNKNOWN_CLASSIFICATION_COVERAGE=1.0
P8_REGISTER_INIT_UNKNOWN_STATIC=30096
P8_REGISTER_INIT_UNKNOWN_SITES=8892
P8_REGISTER_INIT_UNKNOWN_DYNAMIC=26456
P8_REGISTER_INIT_UNKNOWN_WORKLOADS=6
```

The 16 requested mutually exclusive classes partition as follows:

```text
UNKNOWN_P8_REGISTER_INIT=26456
UNKNOWN_OBJECT_IDENTITY=0
UNKNOWN_INDEX_IDENTITY=0
UNKNOWN_LENGTH_IDENTITY=0
UNKNOWN_ALIAS=0
UNKNOWN_CALL_EFFECT=0
UNKNOWN_MUTATION=0
UNKNOWN_LIFETIME=0
UNKNOWN_OVERFLOW=0
UNKNOWN_CFG_PATH=0
UNKNOWN_LOOP_CARRIED_FACT=0
UNKNOWN_REFERENCE=0
UNKNOWN_SLICE=0
UNKNOWN_FAILURE_ORDER=0
UNKNOWN_INSTRUCTION_LIMIT_INTERACTION=0
UNKNOWN_OTHER=0
SUM=26456
```

Every nonzero event has exactly one causal class. The zero rows reflect the
fact that the P9.1 UNKNOWN denominator was already fully assigned to the
register-init class; they do not claim that those mechanisms are globally
absent from the compiler.

## P9 Opportunity Gate

Register initialization belongs to the existing P8 mechanism and is removed
from the P9 bounds/validity denominator:

```text
P9_RELEVANT_UNKNOWN_DYNAMIC=0
INHERENTLY_REQUIRED_DYNAMIC=0
OUT_OF_SCOPE_EXISTING_MECHANISM_DYNAMIC=26456
ATTRIBUTION_LIMIT_ONLY_DYNAMIC=0
POTENTIALLY_AVOIDABLE_UNPROVEN_DYNAMIC=0
PROVABLY_AVOIDABLE_DYNAMIC=0
MAX_THEORETICAL_AVOIDABLE_DYNAMIC=0
MAX_THEORETICAL_SHARE_OF_MODEL=0.0
CONCRETE_REDUNDANT_EXAMPLE_FOUND=NO
MATERIAL_P9_CLASS_FOUND=NO
```

There is no P9-relevant site for which a range fact, object identity, index
identity, length identity, dominance, invalidator closure or failure-order
proof could be specified. The top unknown family is therefore the out-of-
scope P8 family itself:

```text
TOP_UNKNOWN_FAMILY=UNKNOWN_P8_REGISTER_INIT
TOP_UNKNOWN_FAMILY_DYNAMIC=26456
TOP_UNKNOWN_FAMILY_WORKLOADS=6
TOP_UNKNOWN_P9_RELEVANT_SITES=[]
TOP_UNKNOWN_P9_RELEVANT_FAMILIES=[]
```

The machine-readable result contains the ten heaviest concrete P8 examples.
Each uses the structural ledger key and records the current check,
counterexample, possible-redundancy decision and minimum proof boundary.
These examples are evidence for attribution, not candidates for another P9
optimization.

## Closure

```text
P9_3_SELECTION=NO_P9_BOUNDS_OPPORTUNITY
BOUNDS_VALIDITY_LINE_STATUS=CLOSE
P9_PRODUCTION_STARTED=NO
P9_4_AUTHORIZED_BY_EVIDENCE=NO
P9_4_RECOMMENDED_TARGET=NONE
NEXT_GLOBAL_OPTIMIZATION_QUESTION=NO_NEW_TARGET_YET
NEXT_SMALLEST_EXPERIMENT=NONE_WITHIN_P9_BOUNDS
```

Unknown is not an optimization opportunity. The negative result closes the
bounds/validity line without authorizing public proof transport, a stronger
range solver, a P9.4, or production code.

## Integration And Safety

The A+B integration route was analyzed statically. Feature-branch publication
is `PROVEN_ZERO_ACTIONS`; pull-request/ref semantics are `UNKNOWN`; and a
main-ref update is `ACTIONS_POSSIBLE`. No alternative was executed. Thus:

```text
CORRECTNESS_INTEGRATION_ANALYZED=YES
CORRECTNESS_INTEGRATION_PROVENANCE=NOT_PROVEN_ZERO_ACTIONS
CORRECTNESS_INTEGRATED=NO
CORRECTNESS_INTEGRATION=BLOCKED
MAIN_UPDATED=NO
PR_CREATED=NO
PRODUCTION_CODE_CHANGED=NO
BENCHMARK_EXECUTED=NO
GITHUB_ACTIONS_EXECUTED=NO
SHUTDOWN_AUTHORIZED=NO
```

See `CORRECTNESS_A_B_INTEGRATION_20260814.md` for the route table and
`P9_3_RESULT.json` for the complete causal data.
