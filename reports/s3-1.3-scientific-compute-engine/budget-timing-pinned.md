# S3 Performance Report 1.19

## Scope

Portable S3, C, Rust, and Zig workloads are separate from S3-specific engineering cases.

## Repository SHA

adaff49a97c242cd00b15fee4ade565ed0768af2

## Benchmark schema

s3bench 1.0.0

## Hardware

Architecture: x86_64. Detailed CPU and memory metadata remain in raw JSON.

## Operating system

Linux; runner classification: controlled-linux.

## Toolchains

cc: cc (Ubuntu 15.2.0-16ubuntu1) 15.2.0 (O1 native-max-instructions=50000000 native-instruction-budget-mode=exact-segment); cc: cc (Ubuntu 15.2.0-16ubuntu1) 15.2.0 (O1 native-max-instructions=50000000 native-instruction-budget-mode=loop-hybrid); cc: cc (Ubuntu 15.2.0-16ubuntu1) 15.2.0 (O1 native-max-instructions=50000000 native-instruction-budget-mode=per-instruction)

## Power and background-load conditions

Not automatically controlled; authoritative runs require operator documentation.

## Methodology

Build, correctness, warmup, calibration, final samples, summary, export, and comparison are separate phases.

## Measurement scope

Results are partitioned by measurement_scope. KERNEL MEASUREMENTS run an internal loop with loops_per_sample > 1; median_ns_per_loop is a kernel-region cost. PROCESS/STARTUP MEASUREMENTS launch one process per sample with loops_per_sample = 1; median_ns_per_loop is the duration per process/sample and is NOT a kernel cost.

## Warmups

3

## Calibration

Bounded geometric calibration targets the configured sample duration; calibration samples are discarded.

## Samples

15

## Statistics

Median is primary; mean, min, max, sample standard deviation, CV, and nearest-rank p95 are retained.

## Correctness verification

Only checksum-verified cases are measured and eligible for comparison.

## Timed regions

Compile, link, full process, startup, kernel, end-to-end, size, and memory remain distinct fields.

## KERNEL MEASUREMENTS

_Kernel-scoped adapters run an internal loop with loops_per_sample > 1. median_ns_per_loop is comparable across kernel implementations only._

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |

## PROCESS/STARTUP MEASUREMENTS

_Process-scoped adapters launch one process per sample with loops_per_sample = 1; median_ns_per_loop is the duration per process/sample, NOT a kernel cost. S3 native O0 and O1 may be compared within this scope only._

| Benchmark | Implementation | Mode | Optimization | Median ns/process | Loops/process | Median ns/process | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| science.structural-comparison-budget-policy.v1 | s3-exact | native | O1 | 5106336.000000 | 1 | 5106336.000000 | 0.120492 | measured | COMPARABLE |
| science.structural-comparison-budget-policy.v1 | s3-loop-hybrid | native | O1 | 5502227.000000 | 1 | 5502227.000000 | 0.063753 | measured | COMPARABLE |
| science.structural-comparison-budget-policy.v1 | s3-per | native | O1 | 12276743.000000 | 1 | 12276743.000000 | 0.047044 | measured | COMPARABLE |

## Portable suite (legacy view)

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| science.structural-comparison-budget-policy.v1 | s3-exact | native | O1 | 5106336.000000 | 1 | 5106336.000000 | 0.120492 | measured | COMPARABLE |
| science.structural-comparison-budget-policy.v1 | s3-loop-hybrid | native | O1 | 5502227.000000 | 1 | 5502227.000000 | 0.063753 | measured | COMPARABLE |
| science.structural-comparison-budget-policy.v1 | s3-per | native | O1 | 12276743.000000 | 1 | 12276743.000000 | 0.047044 | measured | COMPARABLE |

## S3-specific suite

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |

## S3 emulator

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |

## Interpreted reference

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |

## Compiler pipeline

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |

## Emulator versus native

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |

## O0 versus O1

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |

## Historical baseline

The 0.8 E2 baseline is historical and NOT COMPARABLE for timing by default.

## C comparison

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |

## Rust comparison

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |

## Zig comparison

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |

## Artifact sizes

| Benchmark | Implementation | Artifact bytes |
| --- | --- | ---: |
| science.structural-comparison-budget-policy.v1 | s3-exact | 1276400 |
| science.structural-comparison-budget-policy.v1 | s3-loop-hybrid | 1026024 |
| science.structural-comparison-budget-policy.v1 | s3-per | 851896 |

## Variability

1 measured cases have CV above 0.10; all raw samples are preserved.

## Non-comparable results

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |

## Regressions

No claim without a compatible reviewed baseline.

## Improvements

No claim without a compatible reviewed baseline.

## Known limitations

Shared CI is non-authoritative; missing toolchains and incompatible timed regions remain explicit. Process/startup timing is never normalized against kernel timing.

## Reproduction commands

`python tools/s3bench.py --verify-only`

`python tools/s3bench.py --output-json benchmarks/results/result.json --output-markdown benchmarks/results/report.md`

## Raw result locations

budget-timing-pinned-adaff49.json

## Recommended optimization priorities

Pending validated comparable measurements.
