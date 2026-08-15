# S3-EXP-0033 - P9.1 bounds and validity contract attribution

STATUS=COMPLETE_NO_VALID_TARGET_YET

CAMPAIGN=P9_1_BOUNDS_VALIDITY_CONTRACT_ATTRIBUTION_V1
PRODUCTION_HEAD=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
RESEARCH_HEAD_START=7880ac882db0ff4271e0c32278fef536edbaf579
BENCHMARK_MAIN=0cc0ec659857c48febc9e3919791db0701b02516

QUESTION=Which indexed-memory safety obligations are materially realized in native code, and does a minimum sound local fact model expose a reusable avoidable subset?

MODEL=MODELLED_NATIVE_DYNAMIC_COUNT
MODEL_VERSION=P9_ASSEMBLY_SITE_WEIGHTED_X86_SIDECAR_V1
MODEL_REPRODUCED=YES
MODELLED_DYNAMIC_TOTAL=289500
WORKLOADS=15
CLASSIFICATION_COVERAGE=1.0

TAXONOMY=Negative index, upper bound, array length, slice length, memory initialization, register initialization, object validity, reference validity, slice provenance, mutability/write permission, address validity, failure realization, other safety and unknown were kept separate.

PROFILE=Safety-related explicit realization was 65224 modelled dynamic x86 lines (22.529879101900%). Bounds were 17464 (6.032469775475%); memory initialization was 6660 (2.300518134715%). Hot failure edges were 45840 and cold failure setup had zero modelled dynamic weight under correctness inputs. P8 register initialization was 26456 and was not reselected.

MINIMUM_MODEL=LOCAL_CONSTANTS_PLUS_DOMINATED_TCMP_OPERAND_ALIGNMENT
SUCCESS_EDGE_FACT_SITES=0
LOOP_PROVEN_SITES=0
REPEATED_CHECK_SITES=0
PROVABLY_REDUNDANT_SITES=0
AVOIDABLE_DYNAMIC=0
UNKNOWN_DYNAMIC=26456
FIRST_OBSERVED_BOUNDARY=ASSEMBLY_TO_EMITTER_RANGE_FACT_CONTRACT_NOT_EXPLICIT

NATIVE_PROOF=Focused O0/O1 native correctness passed for array_loop, fixed_array, nested_loop, branch_heavy and tiny_04_arr. The prior P9 native evidence remains the source for the other corpus workloads; no full suite was run.

NEGATIVE_RESULT=Bounds and validity are material, but the current artifacts do not expose a sound reusable object/index/length fact subset. The absence of GCC checks was not used as evidence.

STRONGEST_CANDIDATE=LOOP_PROVEN_BOUNDS_FACT_REUSE
PROMOTION_DECISION=NO_VALID_TARGET_YET
NEXT_DISCRIMINATING_QUESTION=Can a proof-bearing loop-carried access preserve object/index/length identity through the Assembly contract while closing alias, call, mutation, lifetime, overflow and failure-order invalidators?

PRODUCTION_COMPILER_CHANGED=NO
PRODUCTION_BRANCH_CREATED=NO
PRODUCTION_PR_CREATED=NO
EXTERNAL_BENCHMARK_RERUN=NO
GITHUB_ACTIONS_EXECUTED=NO
SHUTDOWN_AUTHORIZED=NO

ARTIFACT=production-reports/p9-1-bounds-validity-contract-20260814/P9_1_RESULT.json

CONCLUSION=P9.1 is complete research only. No P9 production contract is authorized.
