# S3 1.9 Research Questions

Statuses below are checkpoint classifications, not final campaign conclusions.
Primary compiler identity is S3 `211b1aecec756be42516322429720018f54001e7`,
tree `08289d214832e856d46e14ef941239649e9f4063`; the independent matched-run
replication pins the same source commit/tree. Unknown and negative results are
retained.

| ID | Question | Status | Current evidence |
| --- | --- | --- | --- |
| RQ1 | Can S3 map native object instructions and bytes back to compiler origins with materially better coverage than 1.8? | PARTIAL | v4 accounts for every `.text` byte and maps 34.6180%-39.3202% of whole-object instructions, but a material coverage gain over 1.8 is not established; unmapped bytes remain explicit. |
| RQ2 | Can deterministic dynamic structural profiling identify hot compiler-generated regions without PMU? | PARTIAL | Correctness-checked block counters identify hot S3 Assembly blocks without PMU, but the weighted structural counts are not hardware retired-instruction counts or cycle attribution. |
| RQ3 | What categories dominate native execution in the continuity workloads? | PARTIAL | The profiled structural weight is dominated by memory-origin categories (about 48%-52%), with control, constants, moves, and compute also substantial; runtime helpers and intra-block branch skipping limit interpretation. |
| RQ4 | Can native structural evidence identify at least one general optimization opportunity with measurable impact? | PARTIAL | Matched runs show selected budget-policy gains; exact-cell local mutable-load forwarding was rejected with 0/220 eligible loads. No general compiler transformation with measured impact is established. |
| RQ5 | Can reference/alias/effect facts safely authorize a transformation previously blocked by conservative reasoning? | PARTIAL | Fresh O1 analysis of the exact three workload source hashes models 8/8 references with known origins and `NO_ESCAPE` (3 mutable), but keeps `transformation_authorized=false`; the bounded same-block forwarding candidate had 0/220 eligible loads. Facts alone did not authorize or support this candidate. |
| RQ6 | What is the current matched relationship between PER, EXACT and HYBRID? | PARTIAL | EXACT repeats as material for point cloud and raster; HYBRID repeats for point cloud, raster is inconclusive, and energy disagrees across runs. PER remains default. |
| RQ7 | Can S3-Benchmarks independently checkout, build, execute and characterize arbitrary pinned S3 SHAs? | PARTIAL | The lab executor independently verified, built, and correctness-checked one exact pinned S3 SHA. Arbitrary-SHA coverage and failure-mode breadth are not yet qualified. |
| RQ8 | Can historical S3 versions be replayed under a common protocol? | OPEN | Current control and candidate evidence are pinned, but a cross-version replay using a common preserved protocol has not been performed. |
| RQ9 | Can richer induction/dependence analysis reduce vector-legality UNKNOWN classifications? | OPEN | Current O1 reports for the three exact workload sources classify all 5 loops as `UNKNOWN` (0 vectorizable, 0 proven illegal), citing unproven affine induction, unproven access range/origin, and unmodeled general inter-iteration dependence; no richer analysis or transformation was added. Reports: `evidence/vector-legality/*-vector-legality-v1.json`. |
| RQ10 | Do allocator/liveness facts correlate with measured hot stack/memory behavior? | PARTIAL | Current v4 static allocation reports cover 1,024 virtual registers; 6 are stack-resident in one of eight functions, with peak live count 11. Dynamic spills are explicitly not measured, and aggregate hot stack/memory categories do not identify the same allocator values or establish correlation; allocator replacement is not selected. |
| RQ11 | Can compiler-generated structural metrics correlate usefully with runtime? | OPEN | Three workloads and replication disagreement are insufficient for a preregistered correlation analysis; logical structural weight is not hardware execution data. |
| RQ12 | Can bounded fuzzing or metamorphic testing discover optimizer/backend defects outside the existing suite? | OPEN | The existing continuity corpus passed, but no new bounded fuzzing or metamorphic campaign has run. |
| RQ13 | Can structured compiler feedback improve genuinely agent-generated S3 programs? | OPEN | No pinned agent-generated corpus, feedback trial, control group, or output-quality measure has been evaluated. |
| RQ14 | Is an ExecutionContext prototype now justified? | OPEN | The current evidence does not identify an isolation/resource-accounting requirement that demands a new execution-context architecture. |
| RQ15 | Can a useful S3 Compute Profile be defined from proven compiler facts? | OPEN | Dynamic block observations exist, but effects, dependence, portability, and resource facts are not sufficiently complete for a qualified eligibility profile. |
| RQ16 | Do current observations justify Machine IR, SIMD, allocator replacement, portable backend or parallel execution as the next primary frontier? | DEFERRED_WITH_EVIDENCE | No verified Assembly-representation blocker, newly proven vectorizable loop, allocator-dominant runtime cost, alternate-target correctness, or parallel-safety contract currently selects these frontiers. |

The optimization-discovery ranking remains evidence-ranked, not an automatic
decision rule. Ranking v3 consumes current-source reference facts and
per-function static allocation facts in addition to matched runtime and
structural evidence. Reference facts remain diagnostic and do not authorize
automatic source changes. The full Linux suite is complete; final campaign
closure and remaining research frontiers are recorded in `FINAL_REPORT.md`.
No default is promoted.
