# S3 1.6 Native Runtime Efficiency and Budget Architecture

## Result

```text
CAMPAIGN=S3_1_6_NATIVE_RUNTIME_EFFICIENCY_AND_BUDGET_ARCHITECTURE
BASE_MAIN=506108a679f586b5786d0ab020de4e9f10f964f0
CAMPAIGN_BASE=cb88a8036af1bcdc026db193590cb961bee4737d
PR318_STATE=OPEN_DRAFT
FUNCTIONAL_SOURCE_FREEZE=894e7329f21e786d4ab9dfaeed352eaa7e5b0fed
FUNCTIONAL_SOURCE_TREE=51c40d1f54017f6d5f076bf6bca68a85b6311e75
SOURCE_CHANGED_AFTER_FREEZE=NO
FULL_SUITE_HEAD=894e7329f21e786d4ab9dfaeed352eaa7e5b0fed
FULL_SUITE_EXIT=0
```

The 1.6 branch is intentionally based on the unmerged 1.5 candidate in PR #318. The new Draft PR is stacked on `codex/s3-1.5-real-world-compute`; it is not based on `main`. Main was not changed. No merge, release, tag, package publication, or default promotion was performed.

## Budget Architecture

The logical charge point remains one charge immediately before each Assembly instruction executes. A taken branch, call, return, loop instruction, and instruction that would fail all consume their own charge before execution. Thus a budget of `N` permits exactly the first `N` logical instructions; the next instruction fails before its effects. Calls and synchronous callback re-entry continue to share the loaded artifact's process-budget state.

For `PER_INSTRUCTION`, register allocation enabled, and `max_instructions <= INT64_MAX`, the x86-64 emitter now:

1. Reserves `r15` from the allocator and keeps the remaining budget there.
2. Emits `dec r15; js <instruction-limit-failure>` before each logical instruction. A zero remaining budget becomes `-1` and branches to the same diagnostic before the instruction executes.
3. Stores the remaining value in artifact-local data at S3 and foreign-call boundaries. The callee reloads the shared state; this preserves serial nested calls and synchronous FFI callback re-entry.
4. Saves/restores `r15` under the System V ABI and on function returns.

Register-allocation-disabled execution, limits above `INT64_MAX`, `EXACT_SEGMENT`, and `LOOP_HYBRID` retain their established memory-counter paths. The optimization removes repeated memory counter traffic; it does not remove logical charging, exhaustion checks, or diagnostics. Linux native tests cover the preserved `r15` ABI value, exhaustion boundaries, nested calls, and callback re-entry.

The budget state is artifact-local and shared. Concurrent entry to the same loaded artifact from multiple host threads remains unsupported and unqualified. This is the approved clarification of historically unspecified behavior, not a permanent prohibition. Future concurrency requires a separate execution-context, budget ownership, frame-accounting, and synchronization contract.

No source syntax, IR, Assembly format, public C ABI, or default policy changed. `PER_INSTRUCTION` remains the default; `EXACT_SEGMENT` and `LOOP_HYBRID` remain opt-in.

## Answers to the Review Questions

| Question | Evidence-based answer |
|---|---|
| Why was PER slower? | The prior hot path did a memory compare, exhaustion branch, and memory increment for every logical instruction. The eligible optimized path uses a register decrement and sign branch, with synchronization only at defined boundaries. |
| How much is directly attributable? | Static budget-counter memory references fell by 98.1–99.2% (616→12, 1034→8, 1330→18). The emitted check changed from three native instructions to two. The benchmark's overall timing change is measured, but exact cycle-level causal attribution is unavailable without PMU evidence. |
| Which accounting sequence dominated? | The repeated `cmp [__s3_instruction_count], limit; jae failure; inc [__s3_instruction_count]` sequence. The large-limit memory fallback remains intact. |
| Did stack-frame size fall? | No: point cloud +16 B (3632→3648), raster unchanged (4192 B), energy +16 B (2128→2144 B). These are frame sizes, not spill counts. |
| Did static stack traffic fall? | No: 1528→1536, 1807→1821, and 905→907 static stack references. These counts do not prove runtime traffic or spills. |
| Did code size fall? | Yes. `.text` fell 11.3–12.6%; ELF size fell 3.0–4.8% across the three measured kernels. |
| Did helper calls fall? | No. Static call counts stayed at one for each PER workload. |
| Did bounds checks matter? | No bounds-check optimization was made, and this campaign did not isolate bounds checks as the dominant cost. |
| Did register allocation matter? | The allocator now reserves `r15`; this is a targeted register-residency use, not a general allocator algorithm improvement. ABI and call-boundary tests pass. |
| Did real datasets preserve the conclusions? | Real point-cloud and raster fixtures passed bounded native correctness checks. They were not used for the BASE-vs-FINAL timing table; the performance table uses the existing bounded workload fixtures. No real-data performance generalization is claimed. |
| Did agent-generated kernels work? | Five bounded task outputs passed checking, native build/execution, output-reference comparisons, and capacity/error cases. Independent generation required review and corrections, so the result is `PARTIAL`, not fully autonomous qualification. |
| Did PER retain exact semantics? | Yes, for the qualified serial/callback contract and tested budget boundaries. Every Assembly instruction still charges before execution; safe fallbacks remain for ineligible configurations. |
| Did PER remain default? | Yes. No mode promotion occurred. |
| What remains? | Static stack references and frames did not improve; branches and helper calls did not change; the native-vs-C gap remains workload-dependent. Dynamic cycles, actual spills, cache misses, and instruction counts remain unknown because PMU access was unavailable. |

## Native Performance and Code Quality

Protocol: same Linux x86-64 VM and same-process scalar C ABI calls; 3 warmups, 21 samples, 1000 calls per sample; setup/build/input construction outside timing; `ctypes` dispatch included equally; `time.perf_counter_ns`; C reference built with `-O1 -fno-fast-math -ffp-contract=off -fno-tree-vectorize`. PMU was unavailable (`perf_event_paranoid=4`). Raw JSON retains mean, median, p95, min, max, standard deviation, CV, binary hashes, and per-mode metrics.

| Workload | BASE PER median | FINAL PER median | BASE→FINAL | Repeat FINAL median | Final PER / C O1 |
|---|---:|---:|---:|---:|---:|
| Point cloud summary | 32,854.014 ns | 12,865.517 ns | 2.553x faster; 60.8% lower | 13,814.672 ns | 8.448x slower than C |
| Raster window statistics | 25,783.130 ns | 10,902.122 ns | 2.365x faster; 57.7% lower | 11,051.452 ns | 4.678x slower than C |
| PV timeseries aggregation | 38,937.628 ns | 15,538.732 ns | 2.506x faster; 60.1% lower | 15,684.261 ns | 7.557x slower than C |

The repeat differs from the first candidate run by +7.4%, +1.4%, and +0.9%, respectively. These are useful runtime characterizations, not microarchitectural attribution or a universal speedup claim. The original raw JSON's `campaign` field retains the existing 1.5 workload-harness label; the artifacts are unmodified and this report identifies the measurements as the 1.6 candidate experiment.

| Workload / mode | Median ns | `.text` B | ELF B | Frame B | Static instructions | Branches | Memory refs | Stack refs | Budget refs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Point / PER final | 12,865.517 | 58,120 | 258,832 | 3,648 | 4,732 | 1,367 | 1,601 | 1,536 | 8 |
| Point / EXACT | 11,804.119 | 85,293 | 283,280 | 3,632 | 8,594 | 2,281 | 3,890 | 2,635 | 1,172 |
| Point / HYBRID | 11,954.186 | 76,828 | 275,088 | 3,632 | 7,165 | 1,893 | 3,329 | 2,160 | 1,106 |
| Raster / PER final | 10,902.122 | 68,539 | 312,136 | 4,192 | 5,666 | 1,715 | 1,898 | 1,821 | 18 |
| Raster / EXACT | 10,274.800 | 102,316 | 340,680 | 4,192 | 10,399 | 2,891 | 4,786 | 3,110 | 1,592 |
| Raster / HYBRID | 10,577.543 | 89,437 | 328,392 | 4,192 | 8,284 | 2,294 | 3,939 | 2,434 | 1,442 |
| Energy / PER final | 15,538.732 | 36,352 | 160,584 | 2,144 | 2,754 | 789 | 953 | 907 | 12 |
| Energy / EXACT | 15,940.524 | 52,540 | 172,744 | 2,128 | 5,005 | 1,320 | 2,323 | 1,551 | 722 |
| Energy / HYBRID | 14,884.666 | 45,699 | 168,648 | 2,128 | 3,893 | 1,023 | 1,877 | 1,187 | 654 |

For final PER versus the opt-in modes, PER/EXACT median ratios were 1.090x (point), 1.061x (raster), and 0.975x (energy). PER/HYBRID ratios were 1.076x, 1.031x, and 1.044x. No default promotion follows from these measurements.

BASE PER → FINAL PER structural deltas:

| Workload | Static instructions | Static memory refs | Static stack refs | Frame | `.text` | ELF | Calls | Branches | Budget refs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Point | 5,233→4,732 (-9.6%) | 2,619→1,601 (-38.9%) | 1,528→1,536 (+8) | 3,632→3,648 (+16) | 65,774→58,120 (-11.6%) | 266,896→258,832 (-3.0%) | 1→1 | 1,367→1,367 | 1,034→8 (-99.2%) |
| Raster | 6,311→5,666 (-10.2%) | 3,196→1,898 (-40.6%) | 1,807→1,821 (+14) | 4,192→4,192 | 78,460→68,539 (-12.6%) | 324,296→312,136 (-3.8%) | 1→1 | 1,715→1,715 | 1,330→18 (-98.6%) |
| Energy | 3,048→2,754 (-9.6%) | 1,555→953 (-38.7%) | 905→907 (+2) | 2,128→2,144 (+16) | 40,970→36,352 (-11.3%) | 168,648→160,584 (-4.8%) | 1→1 | 789→789 | 616→12 (-98.1%) |

All memory, stack, branch, and instruction counts in these tables are static disassembly metrics. None is labeled as a runtime load, spill, cycle, or cache event.

## Architecture Experiments and Status

```text
BUDGET_SEMANTICS=PASS
BUDGET_ARCHITECTURE_MAP=DOCUMENTED_AND_TESTED
PER_INSTRUCTION_DEFAULT=YES
PER_SEMANTICS_PRESERVED=YES
EXACT_SEGMENT=UNCHANGED_OPT_IN_COMPARATOR
LOOP_HYBRID=UNCHANGED_OPT_IN_COMPARATOR
BASIC_BLOCK_ACCOUNTING=NOT_ADOPTED; EXACT_TRAP_BOUNDARY_NOT_PROVEN
SEGMENT_ACCOUNTING=EXISTING_EXACT_SEGMENT_ONLY; NO_NEW_GENERALIZATION
LOOP_ACCOUNTING=NOT_CHANGED; PER_INSTRUCTION_CHARGING_RETAINED
CHUNKED_ACCOUNTING=NOT_ADOPTED; NO_EXACT_RECOVERY_PROOF
HOT_COLD_PATH_SPLIT=UNCHANGED
BUDGET_STATE_OPTIMIZATION=PASS; RESERVED_R15_WITH_BOUNDARY_SYNC
STATIC_MACHINE_INSTRUCTION_CHANGE=-9.6% TO -10.2%
STATIC_MEMORY_REF_CHANGE=-38.7% TO -40.6%
STATIC_STACK_REF_CHANGE=+2 TO +14 REFERENCES
STACK_FRAME_CHANGE=UNCHANGED TO +16 BYTES
STATIC_CALL_CHANGE=0
TEXT_SIZE_CHANGE=-11.3% TO -12.6%
REGISTER_ALLOCATION_CHANGE=RESERVED_BUDGET_REGISTER_ONLY
HELPER_CALL_CHANGE=NONE
BOUNDS_CHECK_CHANGE=NONE
ADDRESS_CALCULATION_CHANGE=NONE
SIMD=DEFERRED
VECTOR_EXECUTION_NEXT=NO
```

The alternative `cmp/jl/dec` register-check ablation did not provide a consistent runtime advantage across workloads and is not promoted. Existing compact-EA proof gates remain unchanged; failed eligibility does not switch into an unsafe optimized path.

## Workloads, Datasets, and Agent Kernels

The three inherited workloads remain correctness-qualified: point-cloud summary, raster-window statistics, and energy aggregation. All compared budget modes produced matching output hashes in the preserved benchmark JSON.

Two small derived fixtures were qualified with bounded native checks:

* Open3D DemoICPPointClouds `cloud_bin_0.pcd`: downloaded archive SHA-256 `b94e0146c1d48c5edfc11af71b4af39ffca604485668c55a127c3b43203a6bd5`; member SHA-256 `e1e100802c29ef454c6b523084668ee0e2f365ec52eaeebe79ae804c20447b15`; 121 evenly sampled XYZ points; CC BY 3.0 attribution retained.
* USGS historical Elliott Park DRG: source SHA-256 `cd43579caee85145c8d1407349f7de8b3215ed0ef76f563870e5553586fdeca4`; 16×16 crop of 8-bit palette indices; USGS historical map public-domain basis recorded. Values are palette categories, not elevation; the crop has no NoData tag and uses an all-valid mask.

Raw external datasets are not committed. Fixture hashes, source URLs, licenses, retrieval date, and transformations are in `benchmarks/workloads/real_world/public-fixtures-v1/`.

```text
POINT_CLOUD_DERIVED_FIXTURE_SHA256=43a833d9103d178c3c748777de52d35c7eee1b412142e3e1f69b3e75551579f2
PUBLIC_FIXTURE_JSON_SHA256=daf23bc747d7d483391efad709b47ead8854bf2f70405829b2833cd0fee2a924
```

```text
AGENT_KERNEL_TASKS=5
AGENT_KERNEL_GENERATION=PARTIAL
S3_AGENT_COMPUTE_TARGET=PARTIAL_QUALIFICATION
```

The five tasks cover point centroid, point AABB, raster threshold count, raster valid-cell mean, and energy residual summary. The independent agent-generated sources were checked, built, executed under bounded PER, and compared with reference outputs. Human review/correction was necessary after early drafts exposed S3 comparison truth semantics and type-conversion/documentation gaps. The qualified sources therefore prove a real, bounded generation experiment, not fully autonomous success. Tests include invalid shape/range, empty-valid-mask, insufficient output capacity, and oversized output capacity.

```text
WORKLOAD_POINTCLOUD=PASS
WORKLOAD_RASTER=PASS
WORKLOAD_ENERGY=PASS
REAL_POINTCLOUD_DATASET=PASS_BOUNDED_CORRECTNESS
REAL_RASTER_OR_ENERGY_DATASET=PASS_BOUNDED_CORRECTNESS
LOOP_0004=EXPANDED_EVIDENCE; FORMAL_PROMOTION_NOT_ASSERTED
```

Real fixtures strengthen representativeness and correctness; they do not certify scientific or industrial validity, and they do not establish real-dataset performance.

## Validation and Provenance

Windows/local:

```text
python -m compileall bootstrap/s3 tests tools = PASS
git diff --check = PASS
```

Linux focused regression before the final freeze passed for the budget, allocator/liveness/call-aware, native x86-64, FFI, real-workload, and agent-kernel matrices. After the narrow test-contract correction, the affected focused set passed `16` tests, including the Zig toolchain checksum case using a tmpfs cache.

The first full-suite attempt on `71e1d1ac79cee56de8fd5231aad1fc0e199ebe0c` ended `4468 passed, 1 skipped, 5 failed, exit 1`. Four failures were stale assembly-shape assertions for the new `r15` path/save slot; the fifth was Zig cache exhaustion on the full root filesystem. The test expectations were updated and an explicit `>INT64_MAX` memory-fallback regression was added. The Zig test passed when `TMPDIR` and `ZIG_GLOBAL_CACHE_DIR` were directed to `/tmp`; no existing cache or user files were removed.

The final full suite ran once on the corrected freeze:

```text
FULL_SUITE_HEAD=894e7329f21e786d4ab9dfaeed352eaa7e5b0fed
FULL_SUITE_TREE=51c40d1f54017f6d5f076bf6bca68a85b6311e75
FULL_SUITE_START=2026-09-26T19:36:15Z
FULL_SUITE_END=2026-09-26T20:42:58Z
FULL_SUITE_DURATION=4003 seconds
FULL_SUITE_RESULT=4474 passed, 1 skipped, 0 failed, 0 errors
FULL_SUITE_EXIT=0
```

The final stdout transcript and status are preserved under `evidence/full-suite-final-894e7329.*`; the diagnostic transcript is preserved byte-for-byte as `evidence/full-suite-diagnostic-71e1d1ac.log.gz`, with its status alongside it. Linux `compileall` passed on the initial source freeze; after the narrow test-only correction, local `compileall`, the affected Linux focused matrix, and the final Linux full suite passed on `894e7329`. No compiler/runtime/test changes followed `FUNCTIONAL_SOURCE_FREEZE=894e7329...`; only this report and its evidence files are added afterward.

GitHub Actions are supplemental and not required for this campaign; local Linux validation is authoritative. For PR #319, the observed jobs in runs `36271102551`, `36271102602`, and `36271102585` completed with `runner_id=0` and zero steps. GitHub displayed those checks as failures, but no runner executed a test or build step; classify this as `REMOTE_CI_UNAVAILABLE`, not a compiler/test failure. No jobs were rerun. This remote status does not replace or weaken the authoritative local Linux full-suite result above.

## Remaining Bottlenecks and Next Direction

```text
DOMINANT_REMAINING_BOTTLENECKS=
- Static stack references and frame sizes did not fall; actual spills remain unknown.
- Static instruction/text volume remains substantial after removing per-instruction memory counter traffic.
- Native-vs-C gaps remain 4.68x–8.45x on these three bounded workloads; without PMU, the residual dynamic cause is not established.
```

The next evidence-driven direction is **lowering/backend static attribution**, beginning with frame traffic and residual scalar load/store/address sequences. This is a research target, not a claim that register allocation or bounds checks are proven dominant. SIMD remains deferred; branch counts did not change and scalar-vs-memory attribution is still incomplete.

```text
REJECTED_OR_NOT_ADOPTED=
- Whole-block precharging: not adopted because an exact trap/early-exit boundary proof was not established.
- Loop-wide precharging and chunked recovery: not adopted; no proof of exact failure-boundary recovery.
- cmp/jl/dec ablation: no consistent runtime advantage established.
- Compact-EA promotion: not made; existing proof-gated fallback remains.

NEXT_CAMPAIGN_DIRECTION=LOWERING_ARCHITECTURE_STATIC_ATTRIBUTION
EXPANSION_PATH=
REAL_WORKLOAD
-> RESOURCE_BOUNDED_S3
-> EFFICIENT_NATIVE_EXECUTION
-> AGENT_COMPUTE
-> ENGINEERING/SCIENCE CORE
-> PORTABLE_VECTOR/PARALLEL_COMPUTE
```

## Final Gate Values

```text
CAMPAIGN=S3_1_6_NATIVE_RUNTIME_EFFICIENCY_AND_BUDGET_ARCHITECTURE
FUNCTIONAL_SOURCE_FREEZE=894e7329f21e786d4ab9dfaeed352eaa7e5b0fed
PER_INSTRUCTION_DEFAULT=YES
PER_SEMANTICS_PRESERVED=YES
AGENT_KERNEL_TASKS=5
AGENT_KERNEL_GENERATION=PARTIAL
SIMD=DEFERRED
VECTOR_EXECUTION_NEXT=NO
FULL_SUITE=4474 passed, 1 skipped, 0 failed, 0 errors
NATIVE_LINUX=PASS
CHECKSUMS=PRESERVED_IN_evidence/SHA256SUMS.txt
GITHUB_ACTIONS_REQUIRED=NO
GITHUB_ACTIONS=REMOTE_CI_UNAVAILABLE (PR #319; runner_id=0; steps=0; no reruns)
SOURCE_CHANGED_AFTER_FREEZE=NO
PR=319
PR_STATE=DRAFT
MERGE_PERFORMED=NO
RELEASE_CREATED=NO
TAG_CREATED=NO
PYPI_PUBLISHED=NO
DEFAULT_PROMOTED=NO
```
