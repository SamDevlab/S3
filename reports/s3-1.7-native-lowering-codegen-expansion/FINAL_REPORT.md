# S3 1.7 Native Lowering and Codegen Intelligence

## Status

`CAMPAIGN_STATUS=PARTIAL_RESEARCH_CHECKPOINT`

This report closes the register-initialization-marker experiment and records
its validation. It does not claim that every S3 1.7 research axis is complete.
No merge, release, tag, PyPI publication, or default-policy promotion was
performed.

## Provenance

- S3 campaign base: `4ddc7a64a4c395460181db0e8957f085d8bb12a9`
- Source freeze used for native builds: `39dfbb5d19ecefc7df78da7dc8d3ea8e31d81df4`
- Test-contract update: `f0c2963d` (`test(backend): refresh native assembly snapshots`)
- S3 branch: `feat/s3-1.7-native-lowering-codegen-expansion`
- S3-Benchmarks base: `e5f3236f868d5522e1e0e92e245a51c7b3e91064`
- S3-Benchmarks experiment commit: `c0cf2277390f9f530881fa2d60953a63e3992b0f`
- Independent experiment: `EXP-S3-17-LOWERING-002`
- S3-Benchmarks PR: #25, Draft, base `main`
- Control S3 SHA: `4ddc7a64a4c395460181db0e8957f085d8bb12a9`
- Candidate S3 source SHA: `39dfbb5d19ecefc7df78da7dc8d3ea8e31d81df4`
- Raw experiment SHA-256: `571275d03083baa600008916a3d9e7ee4b501b1cdfbfc99f32812963c89ee8cb`

The final full-suite run used the tracked tree represented by `f0c2963d`:
the Linux candidate checkout was at source commit `39dfbb5d`, with only the
assembly snapshot test modified, and that file's Git blob matched the
`f0c2963d` commit. No compiler source changed after the source freeze.

## Change and Attribution

The native x86-64 backend now omits register-initialization markers only where
the existing conservative dataflow proof establishes that the failure is
unreachable. Unsupported functions retain checked behavior. The proof rejects
reference targets, slices, calls, address-taken registers, unknown operations,
and incomplete CFG information rather than weakening safety.

The measured real-world kernels are not eligible for this optimization:
`point_cloud_summary` has 368 registers, `raster_window_statistics` 432, and
`energy_series_aggregation` 211; each analysis returns zero safe reads and
tracks every register because the function has reference targets. Their small
`main` wrappers and the two `absolute_f64` helpers have safe reads, but they
are not the measured hot kernels. This explains why the independent workload
machine-code counters did not change. The next relevant question is whether
reference-heavy functions can gain a narrower proof without compromising
alias/reference safety; this report does not propose relaxing that gate.

The FFI build path also now forwards the selected optimization and syntax mode
to its recompilation. This fixes the earlier mismatch where an O1 experiment
could silently rebuild at the O0 default.

## Validation

- Linux full suite: `4480 passed, 1 skipped, 0 failed`, exit 0.
- The run used Python 3.13.15 on Linux x86-64, with
  `PYTHONDONTWRITEBYTECODE=1`, `ZIG_GLOBAL_CACHE_DIR=/tmp/s3-1.7-zig-global`,
  and pytest's cache provider disabled. Repository tests do not use the
  `request.cache` fixture. The temporary filesystem had 3.6 GiB available;
  the VM's 8 GiB RAM was not increased.
- Full-suite transcript:
  `S3-FULL-SUITE-39dfbb5d-reconciled.log`, SHA-256
  `3bb4e3c56c06f8b61e26f8ff0382d9e3f8b8a748e6409f62ce1e703a1aea9c19`.
- The earlier complete-tree run exited 1: it found stale assembly byte/hash
  expectations after the intentional marker elision and Zig's cache failed
  with `NoSpaceLeft` on the full root filesystem. Its transcript is preserved
  as `S3-FULL-SUITE-39dfbb5d-complete-tree.log`, SHA-256
  `9e4cb4ff0c2c45fa352605d0bc78dd4a5ad7c761d83c75de38eeb50f3b055b8b`.
- The three deterministic assembly snapshots were recalculated from the
  candidate emitter and the focused test passed on Windows and Linux.
- The affected external-toolchain test passed with Zig's cache redirected to
  `/tmp`; no repository data was deleted to free the root filesystem.
- Linux focused CLI/FFI tests: `45 passed`; register-init safety tests:
  `13 passed`; S3-Benchmarks focused tests: `6 passed`.
- `python -m compileall -q bootstrap/s3` passed. S3 `git diff --check` passed
  (PowerShell reported only its LF-to-CRLF working-copy notice).
- No VM memory change was needed.

The old assembly contract was updated because this backend change deliberately
changes emitted assembly. The new expected UTF-8 sizes and SHA-256 values are
stored in `tests/test_exact_segment_instruction_budget.py`.

## Independent Measurement

The experiment used O1, syntax 0.6, baseline native policy, the same pinned
instruction budget, three warmups, 21 paired samples, 1,000 calls per sample,
seed 1701, and 10,000 paired bootstrap resamples. Correctness was checked
before timing; control and candidate outputs matched for all workloads.

| Workload | Static instructions C/N | Memory operands C/N | Branches C/N | Median ns/call C/N | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Energy aggregation | 2763 / 2763 | 953 / 953 | 789 / 789 | 19982.579 / 20296.314 | No material change within 5% |
| Point-cloud summary | 4746 / 4746 | 1601 / 1601 | 1367 / 1367 | 19065.913 / 19314.020 | Inconclusive |
| Raster statistics | 5688 / 5688 | 1898 / 1898 | 1715 / 1715 | 13351.102 / 13637.392 | No material change within 5% |

The observed candidate medians were about 1.9-2.6% slower. The protocol does
not support a material regression or speedup claim. There is no new
C-relative native-gap measurement. The historical campaign baseline remains
workload-specific: point cloud about 8.45x C, raster about 4.68x C, and energy
about 7.56x C; these are not comparable final-candidate results from this
experiment.

`EXP-S3-17-LOWERING-001` remains preserved as diagnostic-only. Its manifest
declared O1 while the then-current FFI rebuild used O0. It was not overwritten
or used as O1 evidence.

## Capability Ledger

- `CODEGEN_PROVENANCE=PARTIAL`: eligibility is explainable through the
  register-initialization proof model, but no general source-to-machine origin
  map or codegen-report command exists yet.
- `MACHINE_CODE_ATTRIBUTION=PARTIAL`: the lab records static instruction,
  memory-operand, and branch counts; source categories and per-region origins
  remain unimplemented.
- `STACK_FRAME_ATTRIBUTION=NOT_MEASURED`
- `STATIC_TRAFFIC_ATTRIBUTION=COUNTS_ONLY`
- `REGISTER_PRESSURE_ANALYSIS=OPEN`
- `CODEGEN_REPORT=NOT_IMPLEMENTED`
- `OPTIMIZATION_EXPLAIN=PARTIAL` (internal proof reason only)
- `PASS_EFFECT_METRICS=NOT_IMPLEMENTED`
- `ABLATION_INFRA=NOT_IMPLEMENTED`
- Move elimination, temporary elision, rematerialization, liveness shrinking,
  register residency, reduction-aware lowering, address strength reduction,
  effective-address lowering, compact-EA, dead-store removal, cold-path
  outlining, and block-layout changes were not evaluated in this checkpoint.
- `PER_INSTRUCTION_DEFAULT=YES` (unchanged)
- `PER_SEMANTICS_PRESERVED=YES`
- `STRICT_FP_PRESERVED=YES` (no floating-point semantics or reassociation
  changes were made)

## Independent Lab State

- `BENCH_REPO=SamDevlab/S3-Benchmarks`
- `BENCH_MAIN_BASE=e5f3236f868d5522e1e0e92e245a51c7b3e91064`
- `BENCH_EXPERIMENT_COMMIT=c0cf2277390f9f530881fa2d60953a63e3992b0f`
- `BENCH_PR=25`, Draft, base `main`
- PR #15 remains OPEN/DRAFT against `main`.
- PR #23 remains OPEN/DRAFT against
  `research/benchmarks-2.2.3-budget-generalization`.
- PR #24 remains OPEN/DRAFT against
  `research/benchmarks-2.2.3-budget-generalization`.
- `HISTORICAL_BUDGET_RECHARACTERIZATION=NOT_RUN`
- `EVIDENCE_LAB_CATCHUP=PARTIAL`: this adds the pinned 1.7 experiment; it does
  not resolve the historical 1.6 budget recharacterization or the existing PR
  stack.
- `CROSS_REPO_PROVENANCE=PASS`
- `S3_BENCHMARK_IMPACT=MATERIAL`
- `EVIDENCE_DEBT=codegen attribution and historical budget recharacterization
  remain open`

## Research Status and Next Frontier

- RQ: Does proven-safe initialization-marker elision materially improve the
  selected real-world workloads? `NO_EFFECT_OBSERVED_WITHIN_PROTOCOL`; those
  measured hot functions are currently ineligible because of reference
  targets.
- RQ: Can machine-code attribution identify the dominant residual costs?
  `OPEN`; the current evidence is aggregate and does not attribute source
  constructs or frame traffic.
- Rejected scope claim: the selected reference-heavy workloads exercise the
  marker-elision fast path. The proof diagnostics show they do not.
- Next recommended target: build a bounded, read-only attribution report for
  one pinned workload, beginning with Assembly function/block and emitted
  native-region counts. Preserve `UNKNOWN` where a source/IR/machine mapping
  cannot be proven. Do not relax the reference safety gate based on aggregate
  timing alone.

## Publication State

- S3 branch: `feat/s3-1.7-native-lowering-codegen-expansion`
- S3 head at report creation: `f0c2963d` plus this report commit
- S3 PR: Draft only; no merge authorized or performed.
- S3-Benchmarks PR #25: Draft only; no merge authorized or performed.
- No release, tag, PyPI publication, default promotion, or shutdown was
  performed.
