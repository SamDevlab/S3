# Milestone 1.17 - Reproducible Benchmark Infrastructure

Status: IMPLEMENTATION COMPLETE - BENCHMARK EXECUTION DEFERRED

## Scope

Milestone 1.17 introduces a portable, correctness-first benchmark subsystem. It
does not alter source semantics, the Python default frontend, the experimental
bounded S3 frontend, public IR 0.6.0, S3 Assembly 0.6.0, the ABI, goldens, or the
historical 0.8 E2 baseline.

## Architecture

ADR-0026 defines `s3bench 1.0.0`. The package lives under
`benchmarks/s3bench/` and the repository CLI is `tools/s3bench.py`. The legacy
0.8 runner remains independently available as `tools/benchmark.py`.

The normative phases are:

1. discover;
2. build;
3. verify;
4. warmup;
5. calibrate;
6. measure;
7. summarize;
8. export;
9. compare;
10. render report.

Build failure, timeout, nonzero status, truncated output, absent checksum, or a
checksum mismatch stops a case before measurement. External commands use
argument lists with `shell=False` and capture stdout, stderr, exit status,
timeout, and bounded output.

## Timing And Calibration

Durations use `time.perf_counter_ns()`. The default protocol uses three warmups,
fifteen final samples, a 200 ms target, at most 1,000,000 loops per sample, and
at most twenty calibration attempts. Calibration scales geometrically and
cannot loop forever. Warmup and calibration observations are excluded from raw
final samples.

Summaries include median, mean, minimum, maximum, sample standard deviation,
coefficient of variation, and nearest-rank p95. Outliers remain present. A CV
above 0.10 adds a warning without deleting samples.

## Data And Privacy

The JSON schema stores workload identity, input identity, checksum status, raw
durations, phase durations, artifact size, optional peak memory, repository
state, OS, architecture, CPU information when detectable, Python/toolchain
versions and flags, runner class, UTC timestamp, notes, and comparability.

Username, private hostname, home directory, personal absolute path, complete
environment, token, credential, IP address, and unnecessary personal identifier
fields are forbidden. Deterministic JSON uses sorted keys and rejects NaN and
infinity. Markdown renders missing values as `unavailable`.

## Baselines And CI

`benchmarks/baseline-0.8-e2.json` is classified as historical. It lacks enough
protocol and environment metadata for conclusive timing comparisons under
`s3bench 1.0.0`, so the loader preserves it as `NOT_COMPARABLE` unless a later
review can prove a narrower compatible subset.

The CI smoke contract covers schema, manifest, discovery, build, checksum, short
execution, deterministic export, and path privacy. Shared runner timing does not
gate performance and is not an authoritative baseline. Workflow activation is
committed with the complete 1.19 structural gate so no benchmark executes during
campaign implementation.

## Authored Coverage

Coverage includes schema and manifest rejection, duplicate IDs, traversal,
safe commands, timeout, checksum failures, warmup exclusion, bounded
calibration, exact sample count, raw preservation, statistics, deterministic
JSON/Markdown, privacy, smoke, verify-only, build-only, historical loading, and
comparison handling.

CREATED - NOT EXECUTED UNTIL MILESTONE 1.19 IMPLEMENTATION COMPLETION
