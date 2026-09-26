# S3 1.5 — Real-World Compute Qualification and Native Gap Closure

## Status

```text
CAMPAIGN=S3_1_5_REAL_WORLD_COMPUTE_QUALIFICATION_AND_NATIVE_GAP_CLOSURE
CAMPAIGN_BASE=506108a679f586b5786d0ab020de4e9f10f964f0
FUNCTIONAL_SOURCE_FREEZE=c924148c6d95948778351c7dd1362259caff670c
FUNCTIONAL_SOURCE_TREE=b54be6f1dc9de47a788f26468c5eb30f7266a646
SOURCE_CHANGED_AFTER_FREEZE=NO
PR317_STATE=MERGED
LINUX_FULL_SUITE=4461_PASSED_1_SKIPPED_EXIT_0
NATIVE_BENCHMARK=PASS
PR=318
PR_STATE=DRAFT
MERGE=NO
RELEASE=NO
TAG=NO
PYPI=NO
DEFAULT_PROMOTION=NO
```

This report records evidence for three bounded scientific/engineering kernel
classes. The datasets are deterministic synthetic fixtures, not field data,
and the results qualify those kernels rather than broad production workloads.
The Python reference compiler remains authoritative; full self-hosting remains
deferred.

## Workloads and correctness

| Workload | External reference | Deterministic dataset | Kernel | Result |
| --- | --- | --- | --- | --- |
| `engineering.point-cloud-summary.v1` | Open3D 0.20.0 plus NumPy | 64-point regular synthetic cloud; SHA-256 `346178eab37077a8bd7989d60836a2b54fb27948c36dabd18e7a58b2e41042f8` | center, axis-aligned bounds, radius-of-gyration reduction | PASS |
| `geospatial.raster-window-statistics.v1` | Rasterio 1.4.4 plus NumPy | 8x8 synthetic EPSG:32613 raster with nodata; SHA-256 `3a182a6f587c30c9f38c0c25dba394729ea4563568dc00e9c3999091a4593f3c` | nodata mask, reductions, threshold count, horizontal absolute gradient | PASS |
| `energy.pv-timeseries-aggregation.v1` | pvlib 0.15.2 plus NumPy | synthetic Denver weather/load week, 168 hourly samples; SHA-256 `dcf7e356a75be9597f2732c1739a2f93f73d657bfdaa4207634aff2e5481afca` | hourly PV output, peak/capacity factor and power-balance aggregation | PASS |

The point-cloud reference uses Open3D's center and axis-aligned bounds; the
radius statistic is a NumPy reduction about that center. Rasterio reads an
in-memory GeoTIFF with explicit CRS, transform, and nodata mask. pvlib computes
the hourly AC series from deterministic synthetic weather; this is not an
observed-weather study. Pinned reference dependencies are in
`benchmarks/references/s3-1.5-requirements.txt`.

All three references matched S3 outputs under the workload contracts
(absolute/relative tolerance `1e-9` for point cloud and raster; `1e-6` absolute
and `1e-9` relative for energy). Hosted and Linux-native execution passed at
O0 and O1 for each workload. The three bounded agent-kernel examples each
passed `s3 check`, FFI compilation, bounded native execution, and reference
result validation. These are pre-authored kernels; no online agent-generation
claim is made.

## Native measurement

The final measurement used Linux x86-64 on an AMD Ryzen 5 3400G, Python 3.14.4,
GNU binutils 2.46, and C `-O1 -fno-fast-math -ffp-contract=off
-fno-tree-vectorize`. For each variant it used three warmups, 21 paired
samples, and 1,000 in-process scalar C ABI calls per sample; build and input
construction were excluded, and the equal ctypes dispatch remained in the
timed region. Paired bootstrap intervals used 10,000 resamples. The exact
source commit/tree and clean-state provenance are embedded in the benchmark
JSON.

| Workload | C O1 median ns/call | S3 O1/PER median ns/call | S3/C | PER/EXACT | PER/HYBRID | PER `.text` bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Point cloud | 1,593.729 | 33,709.833 | 21.15x | 2.802x | 2.770x | 65,774 |
| Raster | 2,476.958 | 25,357.252 | 10.24x | 2.385x | 2.293x | 78,460 |
| Energy | 2,157.542 | 38,476.172 | 17.83x | 2.352x | 2.496x | 40,970 |

PER vs EXACT and PER vs HYBRID were material improvements in paired analysis
for all three kernels. Exact/hybrid `.text` grew versus PER by 29.7%/16.8% for
point cloud, 30.5%/14.0% for raster, and 28.3%/11.5% for energy. These are
measurements of existing opt-in budget modes, not a claim that this campaign
changed the public default. `PER_INSTRUCTION` remains the default.

O0/O1 and compact-EA/baseline comparisons were classified as no material
change within the predeclared 5% threshold. Compact EA was not applied: point
cloud and raster lacked proven index initialization, while the energy kernel
contains reference operations. The no-op/rejection is intentional fail-closed
behavior, not a speedup.

## Cost attribution and decisions

1. **Instruction-budget accounting is the strongest measured cost candidate.**
   Exact-segment and loop-hybrid modes ran about 2.29–2.80x faster than PER
   across these kernels. This is causal mode-comparison evidence, but not a
   PMU-level decomposition and not grounds to change the default.
2. **Generated code and static memory/stack traffic are large secondary
   signals.** At PER, the exported S3 functions contain 3,048–6,311 static
   machine instructions, 1,555–3,196 static memory references, 905–1,807
   static stack references, and 2,128–4,192-byte stack frames. Static counts
   do not establish dynamic loads, spills, or their runtime share.
3. **Bounds/address work, ABI/runtime overhead, and register spills remain
   unquantified.** There is one static call in each measured S3 exported
   function, but this does not identify dynamic helper cost. No spill delta or
   bounds-check reduction is claimed.

The PMU probe was unavailable by policy (`perf_event_paranoid=4`, probe exit
1). Consequently cycles, dynamic instructions, cache behavior, branch misses,
and actual spill/reload counts were not measured. `.text`, instruction,
branch, memory-reference, and stack-reference values are static disassembly
metrics, not dynamic event counts.

The campaign's compiler changes were correctness/contract repairs: preserve
`external`/`exported` function metadata through SSA optimization; classify
slice loads/stores as read/write and alias-observable effects; and forward an
explicit instruction-budget mode through FFI assembly generation while
preserving PER as default. No new general native speed optimization was merged
or promoted. Compact EA was correctly rejected by its proof gates; SIMD was
not implemented because no measured legality/performance case justified it,
and strict floating-point behavior remains unchanged.

The prior 1.4 observation of roughly 11.8x slowdown belongs to a different
structural microbenchmark and is not directly comparable to these workloads.
The current ratios (10.24x–21.15x) are therefore reported per fixture, not as
a campaign-wide improvement over 1.4.

## Gates and provenance

Focused Linux validation on the frozen candidate: 61 passed; Linux
`compileall` exit 0. Full Linux suite on the exact Git checkout and SHA
`c924148c6d95948778351c7dd1362259caff670c`: 4,461 passed, 1 skipped, 0 failed,
0 errors, exit 0. Started `2026-09-26T14:33:59Z`, ended
`2026-09-26T15:38:58Z` (64m59s). The raw progress transcript has 4,461 pass
markers and one skip marker.

An earlier attempted suite is retained as
`evidence/full-suite-invalid-archive.txt` but is **not** counted as candidate
validation: its `git archive` snapshot had no `.git` and its manifest/corpus
bytes did not match the frozen commit; that attempt ended with 11 failures and
113 setup errors, primarily Git-blob-dependent tests, and a Zig build also hit
`NoSpaceLeft` because the VM root filesystem was full. The
valid run used a bundle-derived clean Git checkout at the exact commit and
directed temporary/cache writes to `/tmp`. The separate Python launcher
attempt (missing `python` on noninteractive SSH `PATH`) did not start pytest
and is retained separately.

Evidence files and SHA-256 digests are listed in
`evidence/evidence-hashes.sha256`. The benchmark's raw result is
`evidence/native-workload-benchmark-v1.json`; focused and full-suite transcripts
are preserved beside it.

## Campaign outcome

```text
WORKLOAD_POINTCLOUD=PASS_SYNTHETIC_FIXTURE
WORKLOAD_RASTER=PASS_SYNTHETIC_FIXTURE
WORKLOAD_ENERGY=PASS_SYNTHETIC_FIXTURE
EXTERNAL_REFERENCE_COUNT=3
WORKLOADS_CORRECTNESS=PASS
HOSTED_NATIVE_EQUIVALENCE=PASS_O0_O1
OPTIMIZATION_EXACT_SEGMENT=2.352X_TO_2.802X_FASTER_THAN_PER_OPT_IN
OPTIMIZATION_LOOP_HYBRID=2.293X_TO_2.770X_FASTER_THAN_PER_OPT_IN
COMPACT_EA=NOT_APPLIED_PROOF_GATES
REGISTER_SPILL_CHANGE=UNKNOWN_NOT_DYNAMICALLY_MEASURED
HELPER_CALL_CHANGE=NOT_MEASURED
BOUNDS_CHECK_CHANGE=NOT_MEASURED
BUDGET_OVERHEAD=MODE_COMPARISON_MATERIAL_PER_SLOWER
VECTORIZATION_LEGALITY=NOT_ESTABLISHED
SIMD=DEFERRED
PER_INSTRUCTION_DEFAULT=YES
EXACT_SEGMENT=OPT_IN
LOOP_HYBRID=OPT_IN
AGENT_KERNEL_CORPUS=3_BOUNDED_PREAUTHORED_TASKS_PASS
S3_AGENT_COMPUTE_TARGET=QUALIFIED_WITH_SCOPE_LIMITS
LOOP_0004=QUALIFIED_WITH_SCOPE_LIMITS
GITHUB_ACTIONS_REQUIRED=NO
MERGE=NO
RELEASE=NO
TAG=NO
PYPI=NO
DEFAULT_PROMOTED=NO
```

**Next direction:** investigate budget-check implementation and backend code
quality with dynamic profiling when permitted. Keep register allocation,
vectorization, and SIMD as hypotheses rather than declared bottlenecks until
the relevant evidence exists. Broader non-synthetic datasets and independent
agent-authored kernels are the next scope-expansion gates.
