# S3-EXP-0036 - P10 Global Dynamic Opportunity Census

```text
ID=S3-EXP-0036
STATUS=COMPLETE_NO_VALID_TARGET_YET
CAMPAIGN=P10_GLOBAL_DYNAMIC_OPPORTUNITY_CENSUS_V1
TARGET_KIND=VALIDATED_CORRECTNESS_CANDIDATE_NOT_MAIN
TARGET_SHA=045bbb1427af941b71d28b93cf1e5fe9bf245af7
RELATED_ZETTEL=S3-ZK-0061
```

## Question And Boundary

Where does the current native sidecar cost go, and which families still have
a causally supported chance of being avoidable? P10 is a census, not an
optimization hypothesis. It consumes the validated P9 JSON sidecar and does
not import production modules, compile the candidate, rerun benchmarks or
change the A+B worktree.

P9 is explicitly closed before the census. Its `26456` UNKNOWN events remain
the P8 register-init population and are excluded from P10 as a new opportunity.

## Identity And Baseline

```text
INITIAL_MAIN=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
CORRECTNESS_CANDIDATE_SHA=045bbb1427af941b71d28b93cf1e5fe9bf245af7
TARGET_IS_MAIN=NO
TARGET_IS_VALIDATED_CORRECTNESS_CANDIDATE=YES
TARGET_HEAD_MATCH=YES
TARGET_MAIN_ANCESTRY=YES
EXPECTED_MODELLED_DYNAMIC_TOTAL=289512
BASELINE_REPRODUCED=YES
BASELINE_ACTUAL=289512
WORKLOADS=15
OPTIMIZATION_RUNS=30
CLASSIFICATION_COVERAGE=1.0
```

Every dynamic sidecar line belongs to exactly one primary class. Per-site
identities are structural `function::block::instruction-index::opcode` keys;
Python object identity is not used.

## Primary Dynamic Census

| Rank | Family | Static | Dynamic | Share | Workloads | Nature | Previous status |
| ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | INSTRUCTION_LIMIT_ACCOUNTING | 86202 | 99036 | 34.2079% | 15 | POLICY_REQUIRED | P5/P6 partially exploited |
| 2 | BOUNDS_CHECK | 62018 | 56500 | 19.5156% | 15 | SAFETY_REQUIRED | P9 closed negatively |
| 3 | FRAME_CANONICALIZATION | 30460 | 39081 | 13.4989% | 15 | UNKNOWN | P2/P3/P4 partial; spill unproven |
| 4 | SEMANTIC_PAYLOAD | 29958 | 38050 | 13.1428% | 15 | SEMANTICALLY_REQUIRED | semantic work, not overhead by default |
| 5 | MEMORY_VALIDITY | 30680 | 29408 | 10.1578% | 15 | SAFETY_REQUIRED | P9 closed negatively |
| 6 | BRANCH_CONTROL | 10082 | 19221 | 6.6391% | 15 | SEMANTICALLY_REQUIRED | P7 partial with fallback |
| 7 | EXPLICIT_MEMORY_OPERATION | 6458 | 5772 | 1.9937% | 11 | SEMANTICALLY_REQUIRED | fixed-array reload hypothesis falsified |
| 8 | OTHER_RUNTIME_SAFETY | 334 | 1248 | 0.4311% | 15 | SAFETY_REQUIRED | unsplit sidecar safety class |
| 9 | CALL_ABI_OVERHEAD | 464 | 1196 | 0.4131% | 8 | ABI_REQUIRED | no removal proof |

The primary classes sum to the exact model total. `REGISTER_INITIALIZATION`
is zero in this P10 sidecar because the P9.3 register-init population is
already closed and excluded, not because the mechanism is absent globally.
Likewise, P9.1's `MEMORY_INITIALIZATION=6660` is a subtype overlay inside the
P10 `MEMORY_VALIDITY=29408` primary family and is not added again.

## Necessity Ledger For Top Non-Semantic Families

The five largest non-semantic families are instruction-limit, bounds, frame,
memory validity and branch control. Their ledgers close exactly:

```text
INSTRUCTION_LIMIT_ACCOUNTING: total=99036 required=99036 avoidable=0 potentially=0 unknown=0
BOUNDS_CHECK:                 total=56500 required=56500 avoidable=0 potentially=0 unknown=0
FRAME_CANONICALIZATION:      total=39081 required=0     avoidable=0 potentially=0 unknown=39081
MEMORY_VALIDITY:              total=29408 required=29408 avoidable=0 potentially=0 unknown=0
BRANCH_CONTROL:               total=19221 required=19221 avoidable=0 potentially=0 unknown=0
```

The frame unknown is an avoidability classification, not the P9 UNKNOWN
population. The sidecar observes frame and stack-resident traffic, but does
not establish true spill, reload, ABI save/restore or a removable metadata
chain. The exact overlays are `frame_value_modelled_dynamic=14795` and
`stack_resident_frame_value_modelled_dynamic=10063`; true spill and reload are
`UNKNOWN_NOT_ESTABLISHED`.

Instruction-limit cost remains policy-required under the current evidence.
P5/P6 already simplified parts of its realization, but this census found no
redundant accounting example and does not weaken S3 counting semantics.

## Selection Gate

```text
PROVABLY_REQUIRED_DYNAMIC=250431
PROVABLY_AVOIDABLE_DYNAMIC=0
POTENTIALLY_AVOIDABLE_DYNAMIC=0
UNKNOWN_AVOIDABILITY_DYNAMIC=39081
CONCRETE_AVOIDABLE_EXAMPLE_FOUND=NO
MATERIAL_AVOIDABLE_FAMILY_FOUND=NO
P10_SELECTION=NO_VALID_TARGET_YET
NEXT_GLOBAL_TARGET=NONE
NEXT_DISCRIMINATING_QUESTION=NONE_WITHOUT_A_CONCRETE_AVOIDABLE_EXAMPLE
```

No family satisfies the required conjunction of measured cost, causal
boundary, positive potentially-avoidable population, concrete example,
negative-counterexample search, generality and bounded next experiment.
Therefore P10 ends with a valid negative result rather than selecting the
largest counter.

## Safety And Provenance

```text
PRODUCTION_OPTIMIZATION_STARTED=NO
CORRECTNESS_INTEGRATION_STATUS=STILL_BLOCKED_BY_PROVENANCE
CORRECTNESS_INTEGRATED=NO
GITHUB_ACTIONS_EXECUTED=NO
BENCHMARK_EXECUTED=NO
SHUTDOWN_AUTHORIZED=NO
```

The A+B candidate remains frozen and separate from the research branch. The
integration route was not retried because workflow/provenance state did not
change after P9.3.
