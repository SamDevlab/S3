# P9 causal frame and representation selection checkpoint

```text
CAMPAIGN_ID=P9_CAUSAL_FRAME_REPRESENTATION_ATTRIBUTION_V1
STATUS=COMPLETE_RESEARCH_ONLY
P9_SELECTION=NO_VALID_TARGET_YET
P9_STARTED=NO
PRODUCTION_COMPILER_CHANGED=NO
PRODUCTION_BRANCH_CREATED=NO
PRODUCTION_PR_CREATED=NO
NEW_EXTERNAL_BENCHMARK_TIMING=NO
GITHUB_ACTIONS_EXECUTION=NO
SHUTDOWN_AUTHORIZED=NO
```

## Reconciled anchors

The P8 S3 merge is `5dd6844607ba3a2d5830ed836fb9026eed86d0fb`. The merged
benchmark evidence is on `0cc0ec659857c48febc9e3919791db0701b02516`, and its
measurement harness is `34bb2c7fe743176fed47116d8ce09d0785d2170e`. The six
fixture post-P8 correctness result remains PASS. No benchmark was rerun and
no GitHub Actions run was triggered.

The research checkpoint was based on research head
`5e479bebade21ad6716144664d03e3ceb26f233d`; publication and the resulting
remote research head are verified after validation.

## Causal result

The minimum sound model was a deterministic Assembly-to-x86 sidecar map plus
validated emulator site weights. It reports `MODELLED_NATIVE_DYNAMIC_COUNT`,
not a hardware count. The sidecar identity and model validation passed, and
external correctness passed for all six frozen JSMN fixtures. The model
covered nine internal workloads and six external fixtures. `slice_reference`
was explicitly excluded because the existing emulator does not support TADDR.

The O1 model total was 143151. The largest classes were instruction limit
33.952260%, bounds 19.734406%, frame canonicalization 13.779156%, semantic
payload 12.810948%, and memory validity 10.271671%. Scalar frame-value traffic
was 7807, with 5431 observed stack-resident events, or exactly
3.793895956018% of the O1 model. This is not proof of spills or avoidability.

The fixed-array base-reload hypothesis was falsified for the current shape:
the x86 output already uses direct indexed addressing. Assembly, SSA and
optimized opcode counts aligned in the examined fixed-array, branch-heavy and
JSMN examples. The broad frame family is therefore not established as a
material removable target, and register allocation is not promoted
automatically.

## Selection

The strongest candidate to carry forward is the bounds and validity contract
surface, but no predicate currently proves a safe production rewrite. The
smallest next experiment is a proof-bearing loop-carried TLOAD/TSTORE
bounds/validity sharing or hoisting analysis with initialization,
immutability, instruction-limit, failure-order and checked-fallback controls,
followed by a counterfactual dynamic model. That experiment is outside this
P9 selection checkpoint.

The authoritative machine artifact is
`production-reports/p9-target-selection-frame-representation-20260814/dynamic_attribution.json`
with SHA256
`4D0AC11ED37728ECC3CFCD9F768A5CD199E2DD3C07865EC974EFDA9AD0336C3A`.
