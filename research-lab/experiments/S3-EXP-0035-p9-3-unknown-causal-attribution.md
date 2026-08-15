# S3-EXP-0035 - P9.3 UNKNOWN Causal Attribution

```text
ID=S3-EXP-0035
STATUS=SUPPORTED_NEGATIVE
CAMPAIGN=P9_3_UNKNOWN_CAUSAL_ATTRIBUTION_V1
TARGET_KIND=VALIDATED_CORRECTNESS_CANDIDATE_NOT_MAIN
TARGET_SHA=045bbb1427af941b71d28b93cf1e5fe9bf245af7
RELATED_ZETTEL=S3-ZK-0060
```

## Question

What composes the `UNKNOWN_DYNAMIC=26456` population after P9.2, and does any
remaining class justify another P9 bounds/validity experiment?

P9.3 is an attribution and closure experiment. It does not strengthen range
analysis, add proof plumbing, change Assembly, or import production modules.

## Inputs And Identity

- exact correctness candidate A+B: `045bbb1427af941b71d28b93cf1e5fe9bf245af7`;
- exact detached candidate checkout, with `TARGET_HEAD_MATCH=YES`;
- P9 sidecar model total reproduced at `289512`;
- P9.1 result and its 9060-record structural obligation ledger;
- P9.2 complete classification coverage of `1.0`.

The candidate is not `origin/main`. The historical main anchor remains
`5dd6844607ba3a2d5830ed836fb9026eed86d0fb`.

## Causal Partition

The ledger's `REGISTER_INITIALIZATION_CHECK` native-line population aggregates
to:

```text
P8_REGISTER_INIT_UNKNOWN_STATIC=30096
P8_REGISTER_INIT_UNKNOWN_SITES=8892
P8_REGISTER_INIT_UNKNOWN_DYNAMIC=26456
P8_REGISTER_INIT_UNKNOWN_WORKLOADS=6
```

This is exactly the P9.1 UNKNOWN denominator. Therefore the mutually
exclusive partition is:

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
UNKNOWN_CLASSIFICATION_COVERAGE=1.0
```

Each nonzero event has exactly one class. The zero rows are not newly
invented explanations: P9.1 already assigned the complete UNKNOWN population
to the register-initialization class, so there is no residual event to assign
to a P9 range/validity cause.

## Opportunity Decision

The register-initialization population is an existing P8 mechanism. It is
marked `OUT_OF_SCOPE_FOR_P9_BOUNDS=YES`. A range fact cannot establish that a
register is initialized, and no concrete P9-redundant bounds or validity check
was found. The P9-relevant UNKNOWN denominator is therefore zero:

```text
P9_RELEVANT_UNKNOWN_DYNAMIC=0
INHERENTLY_REQUIRED_DYNAMIC=0
OUT_OF_SCOPE_EXISTING_MECHANISM_DYNAMIC=26456
ATTRIBUTION_LIMIT_ONLY_DYNAMIC=0
POTENTIALLY_AVOIDABLE_UNPROVEN_DYNAMIC=0
PROVABLY_AVOIDABLE_DYNAMIC=0
MAX_THEORETICAL_AVOIDABLE_DYNAMIC=0
MAX_THEORETICAL_SHARE_OF_MODEL=0.0
```

The top family is `UNKNOWN_P8_REGISTER_INIT` with 26456 dynamic events across
six workloads. The top concrete sites and the complete machine-readable
partition are in `P9_3_RESULT.json`; all site identities use the structural
ledger key `function::block::instruction-index::opcode`, never Python object
identity.

No P9-relevant class has a real check, a concrete redundant example, a
bounded proof gap, or a material dynamic population. Negative controls from
P9.2 remain applicable and no new range oracle is justified.

## Selection

```text
CONCRETE_REDUNDANT_EXAMPLE_FOUND=NO
MATERIAL_P9_CLASS_FOUND=NO
P9_3_SELECTION=NO_P9_BOUNDS_OPPORTUNITY
BOUNDS_VALIDITY_LINE_STATUS=CLOSE
P9_4_AUTHORIZED_BY_EVIDENCE=NO
P9_4_RECOMMENDED_TARGET=NONE
NEXT_GLOBAL_OPTIMIZATION_QUESTION=NO_NEW_TARGET_YET
P9_PRODUCTION_STARTED=NO
```

The result closes the P9 bounds/validity line without selecting a replacement
optimization. It is valid to revisit a different measured family only with a
new causal question and a separate authorization.

## Safety And Provenance

```text
PRODUCTION_CODE_CHANGED=NO
BENCHMARK_EXECUTED=NO
GITHUB_ACTIONS_EXECUTED=NO
SHUTDOWN_AUTHORIZED=NO
```

The experiment is research-only and does not integrate the correctness
candidate. The A+B integration route was analyzed statically and remains
blocked by the repository's provenance policy; this negative P9.3 result does
not authorize a workaround.
