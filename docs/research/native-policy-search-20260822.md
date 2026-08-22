# S3 Adaptive Backend Laboratory Notes

These notes record the V2 research boundary. They do not change the S3
language, public API, ABI, or default native backend policy.

## S3-ABL-N001

- `NOTE_ID`: S3-ABL-N001
- `CONCEPT`: INTERFERENCE_REGION_SPILL_PORTFOLIO
- `CURRENT_S3_STATE`: V2 provides deterministic block-region pressure ordering.
- `S3_COMPATIBILITY`: Internal native lowering only.
- `HYPOTHESIS`: Cost-ranked allocation can preserve high-value values when pressure is local.
- `EXPECTED_EFFECT`: Fewer unattractive stack residents in concentrated regions.
- `CORRECTNESS_RISK`: Register coloring or call preservation regression.
- `EXPERIMENTAL_GENE`: `spill_policy=region_aware`.
- `EVIDENCE_REQUIRED`: Verifier, emulator, ABI, determinism, and structural metrics.
- `STATUS`: `ACTIVATED_BLOCK_REGION_SPILL`; full interference-region splitting remains future work.

## S3-RA-N002

- `NOTE_ID`: S3-RA-N002
- `CONCEPT`: LIVE_RANGE_SPLIT
- `CURRENT_S3_STATE`: Conservative copies are materialized at proven loop back-edge boundaries.
- `S3_COMPATIBILITY`: Internal frame-backed boundary only.
- `HYPOTHESIS`: Explicit boundary residence can make availability and pressure observable.
- `EXPECTED_EFFECT`: A measured tradeoff between boundary traffic and live-range continuity.
- `CORRECTNESS_RISK`: Missing incoming-path value or clobbered physical register.
- `EXPERIMENTAL_GENE`: `live_range_split=loop_boundary`.
- `EVIDENCE_REQUIRED`: CFG/liveness proof, native correctness, and copy/load/store metrics.
- `STATUS`: `ACTIVATED_CONSERVATIVE_LOOP_BOUNDARY`.

## S3-RA-N003

- `NOTE_ID`: S3-RA-N003
- `CONCEPT`: REMATERIALIZATION
- `CURRENT_S3_STATE`: Entry-dominated pure `TCONST` values may be recreated when stack-resident.
- `S3_COMPATIBILITY`: Internal Assembly lowering only; initialization checks remain.
- `HYPOTHESIS`: Recreating a constant can avoid a reload without weakening semantics.
- `EXPECTED_EFFECT`: Fewer constant reloads under register pressure.
- `CORRECTNESS_RISK`: Recreating a value before its definition or accepting mutable state.
- `EXPERIMENTAL_GENE`: `rematerialization=const_only`.
- `EVIDENCE_REQUIRED`: Dominance proof, emulator/native correctness, and rematerialization counts.
- `STATUS`: `ACTIVATED_CONST_ONLY`.

## S3-ABL-N004

- `NOTE_ID`: S3-ABL-N004
- `CONCEPT`: PER_FUNCTION_POLICY_PORTFOLIO
- `CURRENT_S3_STATE`: Static `FunctionFeatureVector` decision table is research-only.
- `S3_COMPATIBILITY`: No production integration.
- `HYPOTHESIS`: Generic function shape can select a safer specialized experiment.
- `EXPECTED_EFFECT`: Explainable per-function policy choices.
- `CORRECTNESS_RISK`: Fixture identity or timing leakage into policy selection.
- `EXPERIMENTAL_GENE`: `PerFunctionPolicyPortfolio`.
- `EVIDENCE_REQUIRED`: Feature schema, leave-family-out selection stability, holdout evidence.
- `STATUS`: `RESEARCH_ONLY_NOT_PRODUCTION_INTEGRATED`.

## S3-SCHED-N005

- `NOTE_ID`: S3-SCHED-N005
- `CONCEPT`: POST_SPILL_RESCHEDULING
- `CURRENT_S3_STATE`: No scheduling mutation is attempted in V2.
- `S3_COMPATIBILITY`: Future native backend research.
- `HYPOTHESIS`: Post-spill scheduling may recover some spill-induced latency.
- `EXPECTED_EFFECT`: Potential modeled throughput improvement.
- `CORRECTNESS_RISK`: Changed ordering around checks, calls, or memory effects.
- `EXPERIMENTAL_GENE`: Future `post_spill_reschedule`.
- `EVIDENCE_REQUIRED`: Instruction-level memory/order proof and native correctness.
- `STATUS`: `FUTURE_UNIMPLEMENTED`.

## S3-MEM-N006

- `NOTE_ID`: S3-MEM-N006
- `CONCEPT`: PRESSURE_AWARE_SCALAR_REPLACEMENT
- `CURRENT_S3_STATE`: Only a one-element, address-unescaped, adjacent store/load pair is promoted.
- `S3_COMPATIBILITY`: Internal lowering only; bounds and initialization checks remain.
- `HYPOTHESIS`: Narrow scalar promotion can remove memory traffic without uncontrolled live ranges.
- `EXPECTED_EFFECT`: One store and one load removed for a proven pair.
- `CORRECTNESS_RISK`: Alias escape, call side effects, or changed initialization behavior.
- `EXPERIMENTAL_GENE`: `scalar_promotion=conservative_mem2reg`.
- `EVIDENCE_REQUIRED`: Alias safety, pressure estimate, emulator/native correctness, and memory metrics.
- `STATUS`: `ACTIVATED_CONSERVATIVE_MEM2REG`.

## S3-ABL-N007

- `NOTE_ID`: S3-ABL-N007
- `CONCEPT`: DIVERSITY_PRESERVING_POLICY_SEARCH
- `CURRENT_S3_STATE`: V2 keeps bounded family archives in addition to the global Pareto archive.
- `S3_COMPATIBILITY`: Offline search only.
- `HYPOTHESIS`: Family diversity avoids early convergence on one mechanism.
- `EXPECTED_EFFECT`: More informative bounded experiments.
- `CORRECTNESS_RISK`: Archive members being mislabeled as Pareto-optimal.
- `EXPERIMENTAL_GENE`: Family archive and novelty tie-break.
- `EVIDENCE_REQUIRED`: Candidate ledger, frontier, archive, and deterministic replay.
- `STATUS`: `ACTIVATED_RESEARCH_SEARCH`.

## S3-ABL-N008

- `NOTE_ID`: S3-ABL-N008
- `CONCEPT`: SELF_ADAPTIVE_BACKEND_POLICY_PARAMETERS
- `CURRENT_S3_STATE`: Bounded integer spill coefficients can mutate in the offline genome.
- `S3_COMPATIBILITY`: No default backend integration.
- `HYPOTHESIS`: Small coefficient mutations can explore pressure tradeoffs reproducibly.
- `EXPECTED_EFFECT`: Search-efficiency evidence by candidate evaluation.
- `CORRECTNESS_RISK`: Unbounded or floating-point nondeterminism.
- `EXPERIMENTAL_GENE`: `spill_cost_parameters` integer mutation.
- `EVIDENCE_REQUIRED`: Parent IDs, operator, seed, resulting genome, and hash-seed replay.
- `STATUS`: `RESEARCH_ONLY`.

## S3-ABL-N009

- `NOTE_ID`: S3-ABL-N009
- `CONCEPT`: SEARCH_EFFICIENCY_BY_EVALUATIONS
- `CURRENT_S3_STATE`: V2 reports unique generated/evaluated counts and stage progress.
- `S3_COMPATIBILITY`: Offline search only.
- `HYPOTHESIS`: Evaluation count is more reproducible than wall-clock search duration.
- `EXPECTED_EFFECT`: Comparable search-cost evidence across hosts.
- `CORRECTNESS_RISK`: Hidden duplicate evaluations or holdout feedback.
- `EXPERIMENTAL_GENE`: Fixed-seed staged search.
- `EVIDENCE_REQUIRED`: Progress ledger and candidate ID set.
- `STATUS`: `ACTIVATED_RESEARCH_SEARCH`.

## S3-MEASURE-N010

- `NOTE_ID`: S3-MEASURE-N010
- `CONCEPT`: NORMALIZED_GEOMEAN_WITH_PER_WORKLOAD_GUARDS
- `CURRENT_S3_STATE`: V2 records raw metrics and per-workload ratios; no runtime timing is used.
- `S3_COMPATIBILITY`: Research evidence only.
- `HYPOTHESIS`: Guarded normalization exposes regressions hidden by aggregates.
- `EXPECTED_EFFECT`: Honest structural comparison across heterogeneous cases.
- `CORRECTNESS_RISK`: Treating zero baselines or line counts as runtime proof.
- `EXPERIMENTAL_GENE`: Primary-metric Pareto comparison.
- `EVIDENCE_REQUIRED`: Raw counters, ratios, worst/best/median/geomean when defined.
- `STATUS`: `ACTIVATED_STRUCTURAL_ONLY`.
