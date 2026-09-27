# S3 1.9 Optimization Discovery Ranking

Experimental prioritization only. This report is not an optimization oracle,
does not authorize production changes, and does not promote a default.

Pinned source: `211b1aecec756be42516322429720018f54001e7`

| Rank | Tier | Candidate | Score | Confidence |
| ---: | ---: | --- | ---: | --- |
| 1 | 1 | EXACT_SEGMENT | 0.05727047 | REPEATED_FOR_SELECTED_WORKLOADS_ONLY |
| 2 | 1 | LOOP_HYBRID | 0.02861262 | REPEATED_FOR_SELECTED_WORKLOADS_ONLY |
| 3 | 2 | bounded alias-aware repeated-load/value-locality experiment | 0.12757663 | REPEATED_STRUCTURAL_OBSERVATION_NOT_CAUSAL |
| 4 | 2 | inspect block-local value/materialization and ternary-control lowering | 0.11812416 | STRUCTURAL_TRIAGE_ONLY |

## Boundaries

- `PER_INSTRUCTION` remains the default.
- Paired timing is characterization-only; PMU is unavailable by policy.
- Logical structural weight is not retired instructions, cycles, or causal runtime attribution.
- Candidate transformations require separate semantic proof, correctness gates, and measurement.
