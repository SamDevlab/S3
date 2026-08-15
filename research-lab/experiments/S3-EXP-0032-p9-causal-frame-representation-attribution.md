# S3-EXP-0032 - P9 causal frame and representation attribution

STATUS=COMPLETE_NO_VALID_TARGET_YET

CAMPAIGN=P9_CAUSAL_FRAME_REPRESENTATION_ATTRIBUTION_V1
PRODUCTION_HEAD=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
BENCHMARK_MAIN=0cc0ec659857c48febc9e3919791db0701b02516
BENCHMARK_MEASUREMENT_HEAD=34bb2c7fe743176fed47116d8ce09d0785d2170e

QUESTION=Which semantic lowering family causally accounts for the remaining native representation gap after P8, and is it soundly promotable?

MODEL=MODELLED_NATIVE_DYNAMIC_COUNT
MODEL_SCOPE=Validated Assembly-emulator site weights mapped to deterministic public x86 sidecar lines; this is a modelled count, not a hardware counter.
SIDE_CAR_IDENTITY=PASS
MODEL_VALIDATION=PASS
EXTERNAL_CORRECTNESS=PASS

POPULATION=15 workloads: 9 internal workloads and 6 frozen JSMN fixtures. The slice_reference workload was excluded from dynamic attribution because the existing emulator does not support TADDR; the exclusion was recorded rather than treated as zero.

O1_TOTAL=143151
O0_O1_TOTAL=289500
O1_TOP_CLASSES=INSTRUCTION_LIMIT 33.952260%; BOUNDS_CHECK 19.734406%; FRAME_CANONICALIZATION 13.779156%; SEMANTIC_PAYLOAD 12.810948%; MEMORY_VALIDITY 10.271671%
O1_FRAME_VALUE=7807
O1_STACK_RESIDENT_FRAME_VALUE=5431
O1_STACK_RESIDENT_SHARE=3.793895956018%
TRUE_SPILL_CAUSALITY=NOT_ESTABLISHED
ARRAY_DATA_ACCESS=2.016053%
FIXED_ARRAY_BASE_RELOAD=FALSIFIED_CURRENT_SHAPE

NEGATIVE_RESULT=The broad fixed-array/frame hypothesis is not a material proven-avoidable family. Direct indexed addressing is already emitted; stack residency is observed but does not establish spills or a cheaper legal allocation. The largest safety and instruction-limit classes retain required observers.

STRONGEST_CANDIDATE=BOUNDS_VALIDITY_CONTRACT_SURFACE
PROMOTION_DECISION=NO_VALID_TARGET_YET
NEXT_SMALLEST_EXPERIMENT=Prove a loop-carried TLOAD/TSTORE bounds and validity sharing or hoisting rule with initialization, immutability, instruction-limit, failure-order and checked-fallback obligations, then rerun the counterfactual dynamic model.

PRODUCTION_COMPILER_CHANGED=NO
PRODUCTION_BRANCH_CREATED=NO
PRODUCTION_PR_CREATED=NO
NEW_EXTERNAL_BENCHMARK_TIMING=NO
GITHUB_ACTIONS_EXECUTION=NO
SHUTDOWN_AUTHORIZED=NO

ARTIFACT=production-reports/p9-target-selection-frame-representation-20260814/dynamic_attribution.json
ARTIFACT_SHA256=4D0AC11ED37728ECC3CFCD9F768A5CD199E2DD3C07865EC974EFDA9AD0336C3A

CONCLUSION=P9 selection research is complete. No production P9 implementation is authorized by this result.
