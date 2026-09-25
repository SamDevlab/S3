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

CPython: 3.14.4 (); cc: cc (Ubuntu 15.2.0-16ubuntu1) 15.2.0 (O1 native-max-instructions=50000000 native-instruction-budget-mode=per-instruction); clang: Ubuntu clang version 21.1.8 (6ubuntu1) (-O2 -std=c11 -fno-strict-overflow); rustc: rustc 1.93.1 (01f6ddf75 2026-02-11) (built from a source tarball) (-C opt-level=2 -C overflow-checks=on -C panic=abort); zig: 0.14.1 (-O ReleaseFast)

## Power and background-load conditions

Not automatically controlled; authoritative runs require operator documentation.

## Methodology

Build, correctness, warmup, calibration, final samples, summary, export, and comparison are separate phases.

## Measurement scope

Results are partitioned by measurement_scope. KERNEL MEASUREMENTS run an internal loop with loops_per_sample > 1; median_ns_per_loop is a kernel-region cost. PROCESS/STARTUP MEASUREMENTS launch one process per sample with loops_per_sample = 1; median_ns_per_loop is the duration per process/sample and is NOT a kernel cost.

## Warmups

2

## Calibration

Bounded geometric calibration targets the configured sample duration; calibration samples are discarded.

## Samples

7

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
| science.similarity-distance.v1 | c | native | O2 | 208553581.000000 | 4000 | 52138.395250 | 0.035453 | measured | COMPARABLE |
| science.similarity-distance.v1 | python-reference | interpreted | reference | 272774729.000000 | 64 | 4262105.140625 | 0.035432 | measured | COMPARABLE |
| science.similarity-distance.v1 | rust | native | opt-level=2 | 245072905.000000 | 5000 | 49014.581000 | 0.278442 | measured | COMPARABLE |
| science.similarity-distance.v1 | zig | native | ReleaseFast | 207455778.000000 | 4000 | 51863.944500 | 0.034686 | measured | COMPARABLE |
| science.statistics-matrix.v1 | c | native | O2 | 232125251.000000 | 3000 | 77375.083667 | 0.054073 | measured | COMPARABLE |
| science.statistics-matrix.v1 | python-reference | interpreted | reference | 201077449.000000 | 48 | 4189113.520833 | 0.031439 | measured | COMPARABLE |
| science.statistics-matrix.v1 | rust | native | opt-level=2 | 224124344.000000 | 3000 | 74708.114667 | 0.010197 | measured | COMPARABLE |
| science.statistics-matrix.v1 | zig | native | ReleaseFast | 227930631.000000 | 3000 | 75976.877000 | 0.013166 | measured | COMPARABLE |

## PROCESS/STARTUP MEASUREMENTS

_Process-scoped adapters launch one process per sample with loops_per_sample = 1; median_ns_per_loop is the duration per process/sample, NOT a kernel cost. S3 native O0 and O1 may be compared within this scope only._

| Benchmark | Implementation | Mode | Optimization | Median ns/process | Loops/process | Median ns/process | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| science.similarity-distance.v1 | s3 | native | O1 | 11269447.000000 | 1 | 11269447.000000 | 0.075489 | measured | NOT_COMPARABLE |
| science.statistics-matrix.v1 | s3 | native | O1 | 15821125.000000 | 1 | 15821125.000000 | 0.032301 | measured | NOT_COMPARABLE |

## Portable suite (legacy view)

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| science.similarity-distance.v1 | c | native | O2 | 208553581.000000 | 4000 | 52138.395250 | 0.035453 | measured | COMPARABLE |
| science.similarity-distance.v1 | rust | native | opt-level=2 | 245072905.000000 | 5000 | 49014.581000 | 0.278442 | measured | COMPARABLE |
| science.similarity-distance.v1 | s3 | native | O1 | 11269447.000000 | 1 | 11269447.000000 | 0.075489 | measured | NOT_COMPARABLE |
| science.similarity-distance.v1 | zig | native | ReleaseFast | 207455778.000000 | 4000 | 51863.944500 | 0.034686 | measured | COMPARABLE |
| science.statistics-matrix.v1 | c | native | O2 | 232125251.000000 | 3000 | 77375.083667 | 0.054073 | measured | COMPARABLE |
| science.statistics-matrix.v1 | rust | native | opt-level=2 | 224124344.000000 | 3000 | 74708.114667 | 0.010197 | measured | COMPARABLE |
| science.statistics-matrix.v1 | s3 | native | O1 | 15821125.000000 | 1 | 15821125.000000 | 0.032301 | measured | NOT_COMPARABLE |
| science.statistics-matrix.v1 | zig | native | ReleaseFast | 227930631.000000 | 3000 | 75976.877000 | 0.013166 | measured | COMPARABLE |

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
| science.similarity-distance.v1 | python-reference | interpreted | reference | 272774729.000000 | 64 | 4262105.140625 | 0.035432 | measured | COMPARABLE |
| science.statistics-matrix.v1 | python-reference | interpreted | reference | 201077449.000000 | 48 | 4189113.520833 | 0.031439 | measured | COMPARABLE |

## Compiler pipeline

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |

## Emulator versus native

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| science.similarity-distance.v1 | s3 | native | O1 | 11269447.000000 | 1 | 11269447.000000 | 0.075489 | measured | NOT_COMPARABLE |
| science.statistics-matrix.v1 | s3 | native | O1 | 15821125.000000 | 1 | 15821125.000000 | 0.032301 | measured | NOT_COMPARABLE |

## O0 versus O1

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| science.similarity-distance.v1 | s3 | native | O1 | 11269447.000000 | 1 | 11269447.000000 | 0.075489 | measured | NOT_COMPARABLE |
| science.statistics-matrix.v1 | s3 | native | O1 | 15821125.000000 | 1 | 15821125.000000 | 0.032301 | measured | NOT_COMPARABLE |

## Historical baseline

The 0.8 E2 baseline is historical and NOT COMPARABLE for timing by default.

## C comparison

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| science.similarity-distance.v1 | c | native | O2 | 208553581.000000 | 4000 | 52138.395250 | 0.035453 | measured | COMPARABLE |
| science.statistics-matrix.v1 | c | native | O2 | 232125251.000000 | 3000 | 77375.083667 | 0.054073 | measured | COMPARABLE |

## Rust comparison

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| science.similarity-distance.v1 | rust | native | opt-level=2 | 245072905.000000 | 5000 | 49014.581000 | 0.278442 | measured | COMPARABLE |
| science.statistics-matrix.v1 | rust | native | opt-level=2 | 224124344.000000 | 3000 | 74708.114667 | 0.010197 | measured | COMPARABLE |

## Zig comparison

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| science.similarity-distance.v1 | zig | native | ReleaseFast | 207455778.000000 | 4000 | 51863.944500 | 0.034686 | measured | COMPARABLE |
| science.statistics-matrix.v1 | zig | native | ReleaseFast | 227930631.000000 | 3000 | 75976.877000 | 0.013166 | measured | COMPARABLE |

## Artifact sizes

| Benchmark | Implementation | Artifact bytes |
| --- | --- | ---: |
| science.similarity-distance.v1 | c | 20568 |
| science.similarity-distance.v1 | python-reference | 4203 |
| science.similarity-distance.v1 | rust | 11816560 |
| science.similarity-distance.v1 | s3 | 830832 |
| science.similarity-distance.v1 | zig | 879192 |
| science.statistics-matrix.v1 | c | 20568 |
| science.statistics-matrix.v1 | python-reference | 4203 |
| science.statistics-matrix.v1 | rust | 11816560 |
| science.statistics-matrix.v1 | s3 | 813560 |
| science.statistics-matrix.v1 | zig | 879192 |

## Variability

1 measured cases have CV above 0.10; all raw samples are preserved.

## Non-comparable results

| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| science.similarity-distance.v1 | s3 | native | O1 | 11269447.000000 | 1 | 11269447.000000 | 0.075489 | measured | NOT_COMPARABLE |
| science.statistics-matrix.v1 | s3 | native | O1 | 15821125.000000 | 1 | 15821125.000000 | 0.032301 | measured | NOT_COMPARABLE |

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

science-stats-sim-crosslang-final-adaff49.json

## Recommended optimization priorities

Pending validated comparable measurements.
