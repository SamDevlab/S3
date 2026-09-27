# S3 1.10 Research Questions

Initial questions and inherited evidence at control
`e27dff1e712e50271df9f860669cd714e28f4ce7`. These are not final campaign
conclusions. A hypothesis ranking is prioritization, never transformation
authority.

| ID | Question | Initial status | Inherited evidence / next falsifiable step |
| --- | --- | --- | --- |
| RQ1 | Can S3 identify storage identity and memory versions precisely enough across blocks? | PARTIAL | Bounded exact-cell identity (memory object + constant/SSA index) and CFG availability work on three pinned kernels; this is not general memory versioning. See `MEMORY_TRANSFORM_EXPERIMENTS.md`. |
| RQ2 | Can value availability survive CFG edges under current alias/effect facts? | PARTIAL | Tests prove same-SSA-value joins and reject divergent joins, loop-carried ambiguity, may-alias writes, and unknown calls; unsupported effects fail closed. |
| RQ3 | Can memory intelligence authorize at least one safe transformation with nonzero sites? | PARTIAL | Three research-only proof-gated strategies passed hosted/native correctness on nonzero sites; the direct SSA-value substitution accepted 2/2/6 kernel sites under unique-register/no-phi constraints. None is enabled in production. |
| RQ4 | Does a memory/value transformation materially change native structure or runtime? | PARTIAL | Direct SSA substitution reduced static native memory refs by 10/10/3 and `.text` by 350/350/942 bytes; all paired timing intervals overlap 1. Previous temporary-copy LOAD→LOAD regressed raster. Runtime benefit remains unproven. |
| RQ5 | Which move categories dominate dynamically hot regions? | PARTIAL | Broad MOVE is 33.3–36.6% of weighted native structural syntax; the current category cannot distinguish semantic, ABI, allocator, or temporary moves. See `MOVE_CONTROL_CHARACTERIZATION.md`. |
| RQ6 | Which control-flow categories dominate dynamically hot regions? | PARTIAL | Broad CONTROL_FLOW is 31.4–33.7% of weighted native structural syntax; block-entry instrumentation cannot classify dynamic taken edges or branch roles. No runtime-cause claim. See `MOVE_CONTROL_CHARACTERIZATION.md`. |
| RQ7 | Can dependence analysis reduce vector-legality unknowns? | OPEN | Five loops are unknown due to induction, range/origin, and dependence gaps; add only proof-backed facts. |
| RQ8 | Does value residency trade reduced memory traffic for harmful register pressure? | PARTIAL | Direct SSA substitution reduces static memory references, but raster stack-resident virtuals rise 6→22 and peak live 11→12; temporary-copy variants had much larger growth. Dynamic spills/hardware cause remain unmeasured. |
| RQ9 | Does bounded fuzzing find optimizer/backend defects missed by directed tests? | PARTIAL | `EXP-S3-110-FUZZ-001`: 24 deterministic typed programs checked across reference, O0, O1, and two proof-gated research candidates; zero failures. This bounded corpus found no new defect and does not establish broad coverage. |
| RQ10 | Does metamorphic testing expose optimizer instability? | PARTIAL | The 12 forward/reversed independent-write pairs in `EXP-S3-110-FUZZ-001` agreed, with no instability exposed; this covers only the generator's independent-index writes. |
| RQ11 | Can optimization contracts be machine-readable and explainable? | PARTIAL | `TRANSFORMATION_CONTRACTS.json` records required facts, proof checks, rewrite, postconditions, fallback, implementation, and research-only/non-default status for three strategies. It is not yet consumed by the production optimizer. |
| RQ12 | Can Benchmarks replay multiple historical S3 SHAs under a common protocol? | PARTIAL | Independent serial replay passed for pinned 1.5–1.9 (five SHAs, three workloads each) with identical protocol/host/toolchain and outputs. Cross-version timing deltas remain descriptive because versions were grouped serially; 1.10 awaits a frozen SHA. See Bench `EXP-S3-110-HIST-001`. |
| RQ13 | What is the disposition of historical Bench PRs #15, #23, and #24? | PARTIAL | Current PR states/bases and evidence were audited read-only; recommendations are recorded in the 1.10 Bench historical PR dossier. No historical PR was changed or closed. |
| RQ14 | Can structural/dynamic metrics predict relative runtime usefully? | OPEN | Three workloads and replication are insufficient; preregister scope and avoid treating logical structural weight as hardware cost. |
| RQ15 | Do real agent-generated S3 programs improve with structured compiler feedback? | OPEN | No controlled corpus exists; only proceed if an actual agent/model capability is available and raw prompts/results can be pinned. |
| RQ16 | Can S3 define a useful Compute Profile from proven facts? | OPEN | Effects, dependence, portability, and resource facts are incomplete; derive eligibility only from existing proof-grade fields. |
| RQ17 | Does a discovered optimization justify Machine IR? | DEFERRED_WITH_EVIDENCE | No concrete Assembly representation blocker has been shown; reopen only with a transformation that cannot be expressed safely at current IR. |
| RQ18 | Does a proven hot loop justify experimental SIMD? | DEFERRED_WITH_EVIDENCE | No loop is currently proven vectorizable; no SIMD until legality facts and workload relevance change. |
| RQ19 | Is allocator redesign, portable backend, ExecutionContext, or parallel work justified? | DEFERRED_WITH_EVIDENCE | Current evidence does not isolate allocator causality, a required second target, execution-isolation need, or parallel-safe workload. |
| RQ20 | What is the dominant next frontier after the memory/value investigation? | OPEN | Decide from measured eligibility, proof completeness, transformation results, and independently replicated native impact. |

## Carry-forward negative results

- Exact-cell, same-block mutable-load forwarding: `REJECTED_NO_ELIGIBLE_REPEATED_MUTABLE_LOADS` for 0/220 sites. Do not reintroduce the same predicate under another name.
- Inherited memory-origin share (48-52%) is a structural estimate, not a runtime-causality claim.
- Vector legality: 5 `UNKNOWN`, 0 proven vectorizable, 0 proven illegal.
- Static stack residence is not a dynamic spill count.
- PMU access is unavailable by policy; do not infer cycles or retired operations.
- Temporary-copy cross-block LOAD→LOAD reuse is not generally beneficial; the raster native candidate is a measured material regression. Direct SSA-value substitution reduces static references but has much stricter eligibility and inconclusive timing.
