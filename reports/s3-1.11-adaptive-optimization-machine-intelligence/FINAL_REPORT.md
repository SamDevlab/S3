# S3 1.11 Final Research Report

## Outcome

The bounded research campaign is complete for this candidate. All compiler
production files remain unchanged; the work consists of isolated research
tools, tests, reports, and evidence. No optimization was promoted, no default
changed, and no release or tag was created. Publication remains two Draft PRs
and a human review gate.

```text
CAMPAIGN=S3_1_11_ADAPTIVE_OPTIMIZATION_REGISTER_MEMORY_CODESIGN_MACHINE_INTELLIGENCE_AND_EXPERIMENTAL_COMPUTE_FRONTIER
S3_CAMPAIGN_BASE=832b1cc04fe1f6174e482eb3a245e08af3d53211
S3_CONTROL_SHA=832b1cc04fe1f6174e482eb3a245e08af3d53211
S3_CONTROL_TREE=dc1138890655169088f9371ce32a9050cfc3af8d
S3_FUNCTIONAL_SOURCE_FREEZE=832b1cc04fe1f6174e482eb3a245e08af3d53211
S3_FUNCTIONAL_SOURCE_TREE=dc1138890655169088f9371ce32a9050cfc3af8d
PER_INSTRUCTION_DEFAULT=YES
STRICT_FP_PRESERVED=YES
PRODUCTION_COMPILER_SOURCE_CHANGED=NO
PRODUCTION_DEFAULT_CHANGED=NO
RELEASE_OR_TAG_CREATED=NO
```

## Validation

```text
S3_FOCUSED_TESTS=53 passed on Windows; 53 passed on Linux
S3_COMPILEALL=PASS on Windows
S3_FULL_LINUX_SUITE=4589 passed, 1 skipped, 0 failed, exit 0
S3_FULL_LINUX_SUITE_HEAD=832b1cc04fe1f6174e482eb3a245e08af3d53211
S3_FULL_LINUX_SUITE_TRANSCRIPT=evidence/validation/FULL-LINUX-SUITE-832b-20260928T01.txt
S3_FULL_LINUX_SUITE_TRANSCRIPT_SHA256=85d0afde7e28b33d54d94640ab8fb75b168fb4e42c8834658eba33b128c00739
BENCH_FULL_LINUX_SUITE=42 passed, exit 0
BENCH_FULL_WINDOWS_SUITE=41 passed, 1 skipped, exit 0
BENCH_COMPILEALL=PASS on Windows
NATIVE_LINUX_CORRECTNESS=PASS for pinned baseline and tested candidates
INDEPENDENT_BENCH_REPLAY=PASS for hot-fallthrough correctness and static metrics
```

The full S3 Linux gate used the exact frozen source SHA and hash-matched all 30
S3 1.11 test/tool files as they stood during that run. Afterward, two tests
had only their extra blank line at EOF removed to satisfy the staged whitespace
check; the final versions were rerun together on Linux (3 passed, exit 0).
No test logic changed. To avoid writing into the VM's full root filesystem,
pytest temporary data and compiler caches were directed to the available
`/dev/shm` scratch. The transcript contains the terminal exit code and UTC
start/end. The first Bench Linux collection attempt lacked the S3 checkout on
`PYTHONPATH` and ran no tests; the corrected full suite passed and its separate
transcript is retained in the Bench report.

## Scientific Findings

- **Value and memory:** dominating SSA substitution consistently improves
  structure, but the raster case increases pressure and stack residency. The
  conservative guard keeps the structurally safer energy/point-cloud cases and
  rejects raster. STORE→LOAD forwarding lowers some code-size measures but
  increases memory references and pressure on all three workloads. Point-cloud
  timing has a material characterization signal replicated on the exact
  binaries, but it is workload-specific and does not establish a causal model.
- **Liveness and registers:** both value rewrites increase CFG-aware live-set
  incidence. The evidence supports pressure-aware gating and lifetime analysis;
  it does not establish an allocator bottleneck or justify allocator redesign.
- **Moves:** 30 same-color TMOV data bodies were omitted in an isolated
  prototype with allocation and PER accounting unchanged. Static instructions
  and `.text` decreased for all workloads; timing did not materially change.
  Broad MOVE origin still cannot be separated into semantic, ABI, and allocator
  causes with current provenance.
- **Control and profiles:** exact edge counts are available only where a
  profiled `TJMP` block has one successor. This gives 26 exact edges in the
  reported top-20 hot-block subsets; 93 `TBR3` conditional edges remain
  unknown. One 168-execution hot backedge became fallthrough, removing one
  static branch/instruction and two `.text` bytes. Paired timing remained
  within the ±5% materiality band, and the Bench lab independently reproduced
  exact outputs and static metrics.
- **Addresses and loops:** the tested point-cloud address recurrence worsened
  every reported static dimension except pressure, with inconclusive timing,
  and was rejected. Loop analysis resolved scalar bounds for the pinned
  workloads and proved no slice/reference writes in five loop regions, but
  whole-loop independence remains unproven for 0/5 loops. Vector authority and
  SIMD remain absent.
- **Verification:** the bounded deterministic corpus covers 100 programs and
  50 independent-write plus 50 same-storage metamorphic controls, with zero
  mismatches. This is not general-language fuzzing.
- **Architecture:** tested transformations were expressible in existing
  source/IR/Assembly research paths. Current evidence does not justify
  Machine IR, MemorySSA, a new allocator, O2, or production wiring.

The evidence-backed candidate comparisons are in
`OPTIMIZATION_PARETO.md`; experiment-by-experiment outcomes and all RQ1–RQ30
statuses are in `EXPERIMENT_MATRIX.md` and `RESEARCH_QUESTIONS.md`.

## Campaign Closure Scorecard

```text
REGISTERED_EXPERIMENTS=25 (includes baseline, analyses, and superseded diagnostics)
BOUNDED_TRANSFORMATION_CANDIDATES=5 (two value rewrites, same-color copy omission, one address recurrence, one hot fallthrough)
VALUE_LOCALITY_ANALYSIS=PARTIAL
LIVE_RANGE_ANALYSIS=SUPPORTED_STRUCTURALLY
LIFETIME_SHRINKING=NOT_TESTED
VALUE_RESIDENCY=NOT_TESTED
REMATERIALIZATION=NOT_TESTED
REGISTER_PRESSURE_MODEL=PARTIAL (peak-live and static stack-residency facts; no dynamic spill count)
REGISTER_MEMORY_COST_MODEL=PARTIAL (conservative Pareto guard; runtime direction not predicted)
STACK_RESIDENCY_ANALYSIS=SUPPORTED_STRUCTURALLY (static allocation metric only)
MOVE_PROVENANCE=PARTIAL (30 same-color copies tested; broad move causes remain unknown)
CONTROL_PROVENANCE=PARTIAL (26 single-successor edges exact; 93 conditional edges unknown)
ADDRESS_PROVENANCE=PARTIAL (bounded forms attributed; recurrence candidate rejected)
HOT_MOVE_WEIGHT=51326 / 43064 / 28594 (energy / point cloud / raster weighted structural category; not runtime share)
HOT_CONTROL_WEIGHT=44140 / 38437 / 28933 (same workloads and interpretation)
HOT_ADDRESS_WEIGHT=NO_DEDICATED_CATEGORY; memory-access origin weights are 72465 / 63438 / 41378 and must not be interpreted as address-generation cost
LOOP_CANONICALIZATION=PARTIAL
INDUCTION_ANALYSIS=PARTIAL (one update on all 5 abstract backedge states; no full legality proof)
ACCESS_FUNCTION_ANALYSIS=PARTIAL (bounded access shapes and scalar bounds only)
DEPENDENCE_ANALYSIS=PARTIAL (no slice/reference writes in 5 regions; whole-loop independence 0/5)
VECTORIZABLE_LOOP_COUNT=0
NOT_VECTORIZABLE_LOOP_COUNT=0
UNKNOWN_VECTOR_LOOP_COUNT=5
SIMD=NOT_AUTHORIZED; NO SIMD TRANSFORM RUN
O2_EXPERIMENTAL=NOT_CREATED
MACHINE_IR=NOT_JUSTIFIED
MACHINE_IR_JUSTIFIED=NO
MEMORY_SSA=NOT_JUSTIFIED
MEMORY_SSA_JUSTIFIED=NO
ALLOCATOR_REDESIGN_JUSTIFIED=NO
PROFILE_GUIDED_OPTIMIZATION=PARTIAL (deterministic logical profiles; bounded layout experiment)
HOT_BLOCK_LAYOUT=SUPPORTED_STRUCTURALLY; NO MATERIAL TIMING CHANGE
COLD_PATH_SPLITTING=NOT_TESTED
AUTOTUNING=NOT_RUN
SUPEROPTIMIZATION=NOT_RUN
EQUALITY_SATURATION=NOT_RUN
AGENT_NATIVE_EXPERIMENT=NOT_RUN
S3_COMPUTE_PROFILE=NOT_QUALIFIED
PARALLEL_LEGALITY=NOT_PROVEN
SECOND_TARGET_PROBE=NOT_RUN
EXECUTION_CONTEXT=NOT_TESTED
COMPILE_TIME_METRICS=NOT_MEASURED
PASS_TIMING=NOT_MEASURED
BINARY_METRICS=STATIC_NATIVE_OBJECTS_MEASURED
CODE_SIZE_ANALYSIS=STATIC_TEXT_AND_OBJECT_DIMENSIONS_MEASURED
FUZZ_CASES=100
FUZZ_FAILURES=0
METAMORPHIC_CASES=100 (50 independent-write pairs + 50 same-storage controls)
METAMORPHIC_FAILURES=0
PER_INSTRUCTION_DEFAULT=YES
PER_SEMANTICS_PRESERVED=YES
STRICT_FP_PRESERVED=YES
NATIVE_TIMING_CLASS=CHARACTERIZATION_ONLY
NATIVE_SPEEDUP_CLAIM=NO
HARDWARE_COUNTERS=UNAVAILABLE_BY_POLICY (perf_event_paranoid=4)
PMU=UNAVAILABLE
SOURCE_CHANGED_AFTER_FREEZE=NO (production compiler source; research tools/tests/reports are the 1.11 deliverables)
```

The most material positive timing observation is one replicated,
workload-specific point-cloud STORE→LOAD characterization signal on identical
native binaries; its structural trade-offs remain, its cause is unestablished,
and the conservative policy still rejects the candidate. The hot-fallthrough
change is structural only. Neither result changes a compiler default or
constitutes a general speedup claim. Detailed status for every RQ is in the
closure table, including questions intentionally left open or untested.

## Remaining Questions and Next Frontier

```text
PRIMARY_NEXT_FRONTIER=PRESSURE-AWARE VALUE LOCALITY AND NARROW RUNTIME CAUSALITY
SECONDARY_NEXT_FRONTIER=CONDITIONAL EDGE COUNTS AND LOOP LEGALITY
MACHINE_IR_JUSTIFIED=NO
MEMORY_SSA_JUSTIFIED=NO
ALLOCATOR_REDESIGN_JUSTIFIED=NO
SIMD_JUSTIFIED=NO
```

The first recommendation follows from the contrast between the guarded SSA
substitution structural wins, the raster pressure rejection, and the
workload-specific STORE→LOAD timing signal despite worse pressure/traffic. The
secondary frontier follows from 93 unknown conditional edges and five loops
without whole-loop independence proofs. These are recommendations for human
selection only; this report does not start a 1.12 campaign.

## Evidence and Publication Gate

The retention decision and local-only raw artifacts are listed in
`EVIDENCE_POLICY.md`. Large native-observatory dumps and the raw live-range
snapshot remain preserved locally but are excluded from the planned PR; compact
summaries, hashes, experiment results, tools, and tests remain reviewable.

```text
S3_BRANCH=feat/s3-1.11-adaptive-optimization-machine-intelligence
S3_PR_BASE=main
S3_PR_NUMBER=325
S3_PR_URL=https://github.com/SamDevlab/S3/pull/325
S3_PR_STATE=OPEN_DRAFT
S3_INITIAL_PUBLICATION_COMMIT=f2084e8d22c3749a385668d6f530c8c06e596bfd
S3_EVIDENCE_FILE_COUNT=73
S3_EVIDENCE_TOTAL_BYTES=1340746 (all 73 published blobs, including tools/tests)
S3_LARGEST_COMMITTED_ARTIFACT=reports/s3-1.11-adaptive-optimization-machine-intelligence/evidence/control-832b/EXP-S3-111-EDGE-PROFILE-001.json,217225
INTERMEDIATE_ARTIFACTS_COMMITTED=0 generated binaries/caches; superseded diagnostic JSON retained intentionally
LARGE_RAW_EVIDENCE_ARTIFACTS_COMMITTED=0 (4 excluded files preserved locally)
BENCH_BRANCH=research/s3-1.11-adaptive-optimization-lab
BENCH_PR_BASE=main
BENCH_PR_NUMBER=29
BENCH_PR_URL=https://github.com/SamDevlab/S3-Benchmarks/pull/29
BENCH_PR_STATE=OPEN_DRAFT
STOP_HUMAN_GATE=REVIEW_S3_1_11
```
