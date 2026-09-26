# S3 1.4 Scientific Optimizer and Domain Compute

## Candidate and gates

- Campaign branch: `feat/s3-1.4-scientific-optimizer-domain-compute`
- Source candidate tested: `b24b17dabf692352baabfcd0ebc85f207fad5ab8`
- Source tree was clean for the Linux gates and both final benchmark runs.
- Base at final reconciliation: `origin/main` = `13a5a8308064e8277887fecc6052cde6b22115f3`.
- Linux host: x86-64, AMD Ryzen 5 3400G, Python 3.13.15.
- Focused benchmark-harness tests: 6 passed.
- `python -m compileall -q bootstrap tests tools`: PASS.
- `git diff --check`: PASS.
- Full suite: 4,437 passed, 1 skipped, 0 failed, 0 errors; 4,438 selected; exit 0.
- Full-suite interval: 2026-09-26 05:07:00 to 06:13:45 UTC (4,005 seconds).

The full-suite command ran against the exact source candidate above. The repository's duplicated quiet options suppress pytest's textual count summary, so the counts were reconciled from the preserved 4,438 collected node IDs and terminal progress transcript (4,437 pass markers and one skip marker). The node ID inventory, raw transcript and status are preserved under `evidence/`.

## Implemented scope

The candidate adds the scientific optimizer/geometry workload work already described by the campaign: conservative, proof-gated bounded vector bounds elimination; loop/range and reduction recognition metadata; geometry standard-library APIs and a deterministic point-cloud/mesh workload integrated with S3Bench; and benchmark characterization tools for instruction-budget policies and equivalent native kernels.

Reduction recognition remains metadata only: it does not reassociate floating-point operations or enable vectorization. Bounds-check elimination is applied only where the optimizer has a valid proof; address escape and overflow-sensitive cases remain conservative. The default instruction-budget mode remains `PER_INSTRUCTION`.

The final review also fixed the native benchmark harness to load S3's actual exported symbol (`s3_kernel`) while C, Rust and Zig continue to export `kernel`. Repeated in-process calls share the S3 artifact's finite instruction counter, so the benchmark now sets and records an explicit 100,000,000-instruction ceiling. No production backend behavior was changed for this harness correction.

## Native kernel characterization

Protocol: Linux x86-64, O1, same scalar C ABI and left-to-right squared-radius accumulation, 1,000 iterations per call, three warmups, 21 paired samples, rotating implementation order. Build/load/setup were outside the timed region. Expected checksum: `18078.125`; every implementation matched. The S3 FFI build used the recorded 100,000,000 instruction ceiling. This is characterization, not a native speedup claim.

| Implementation | Median ns/call | P95 ns/call | `.text` bytes | Checksum |
|---|---:|---:|---:|---|
| S3 | 42,830 | 44,169 | 10,515 | PASS |
| C | 3,640 | 4,050 | 283 | PASS |
| Rust | 3,640 | 3,750 | 375 | PASS |
| Zig | 3,640 | 3,760 | 346,538 | PASS |

The paired bootstrap comparison classified C, Rust and Zig against S3 as `REGRESSION` in all three cases. Reference/S3 median ratios were 0.0849 (C), 0.0846 (Rust) and 0.0850 (Zig); these are not speedups. `native_speedup_claim` is false in the raw result. These results expose substantial remaining native-kernel overhead and do not justify changing defaults or claiming performance parity.

## Instruction-budget characterization

Protocol: the same O1 `AssemblyProgram` for each kernel, changing only `instruction_budget_mode`; 500 repeated kernel executions per process, two warmups and nine paired samples per mode/kernel. All three modes (PER, EXACT and HYBRID) passed correctness for DOT, RMSD and variance.

| Kernel | Median ns PER / EXACT / HYBRID | `.text` bytes PER / EXACT / HYBRID | EXACT vs PER | HYBRID vs PER |
|---|---|---|---:|---:|
| DOT | 3,143,371 / 1,568,506 / 1,524,466 | 180,530 / 236,229 / 203,723 | 2.085x improvement | 2.145x improvement |
| RMSD | 3,788,622 / 1,770,192 / 1,896,061 | 180,530 / 236,229 / 203,723 | 2.292x improvement | 2.008x improvement |
| Variance | 5,817,062 / 2,593,670 / 2,850,256 | 180,354 / 235,966 / 203,460 | 2.166x improvement | 2.041x improvement |

Across these kernels, EXACT increased `.text` by about 30.8% versus PER; HYBRID increased it by about 12.8%. The timing improvements and code-size costs are workload-specific characterization only. `PER_INSTRUCTION` remains the default; no mode promotion is requested by this report.

## Evidence and publication state

Raw full-suite output, status, successful benchmark JSON/stdout, failed harness diagnostics, and SHA-256 hashes are retained in `evidence/`. The failed benchmark attempts produced no valid timing results: the initial run exposed the incorrect S3 symbol lookup; later attempts exposed the default instruction ceiling being exhausted across repeated calls. Both causes were corrected before the successful runs recorded above.

- `FINAL_TESTED_SOURCE_HEAD=b24b17dabf692352baabfcd0ebc85f207fad5ab8`
- `SOURCE_CHANGED_AFTER_FINAL_GATES=NO` (the remaining planned changes are this report and raw evidence only).
- Merge, release, tag and default-policy promotion: not performed.
- This campaign's negative cross-language timing result is explicitly retained; it is not hidden by the instruction-budget mode improvements.
