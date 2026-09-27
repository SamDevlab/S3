# S3 1.9 Optimization Discovery Ranking

Experimental prioritization only. This report is not an optimization oracle,
does not authorize production changes, and does not promote a default.

Pinned source: `211b1aecec756be42516322429720018f54001e7`

| Rank | Tier | Candidate | Score | Confidence |
| ---: | ---: | --- | ---: | --- |
| 1 | 1 | EXACT_SEGMENT | 0.05727047 | REPEATED_FOR_SELECTED_WORKLOADS_ONLY |
| 2 | 1 | LOOP_HYBRID | 0.02861262 | REPEATED_FOR_SELECTED_WORKLOADS_ONLY |
| 3 | 2 | memory-origin reduction beyond same-block exact-cell forwarding | 0.12757663 | REPEATED_STRUCTURAL_OBSERVATION_NOT_CAUSAL |
| 4 | 2 | inspect block-local value/materialization and ternary-control lowering | 0.11812416 | STRUCTURAL_TRIAGE_ONLY |

## Boundaries

- `PER_INSTRUCTION` remains the default.
- Paired timing is characterization-only; PMU is unavailable by policy.
- Logical structural weight is not retired instructions, cycles, or causal runtime attribution.
- Candidate transformations require separate semantic proof, correctness gates, and measurement.

## Reference and Allocator Context

Reference reports cover 8 modeled references: 8 known-origin and 8 `NO_ESCAPE`; 3 are mutable. These remain diagnostic facts and do not authorize transformations.
Static allocation reports cover 1024 virtual registers; 6 are stack-resident across 1 function(s). Dynamic spills: `NOT_MEASURED`.
The allocator-replacement frontier is not selected from these static counts; they do not explain dynamic native stack or memory cost.

## Completed Candidate Experiment

`EXP-S3-19-OPT-001`: **REJECTED_NO_ELIGIBLE_REPEATED_MUTABLE_LOADS**; 0 of 220 mutable loads were forwarded.
The exact same-cell, same-index-version, same-block rule found no eligible pair in the three workloads; broader memory-origin optimization remains open.
Correctness matched baseline and references; no timing or PMU claim was made.
