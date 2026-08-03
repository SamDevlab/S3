# ADR-0026: Reproducible Benchmark Protocol And Result Schema

Status: Accepted

## Context

ADR-0015 established the first S3 performance-measurement policy and the 0.8
runner added useful in-process timing and deterministic structural baselines.
That infrastructure does not yet define a portable result record, bounded
calibration, cross-toolchain execution, or compatibility rules for comparing
measurements collected by different protocols.

Milestones 1.17 through 1.19 need one auditable protocol for S3 emulator and
native execution, compiler phases, C, Rust, and Zig. Correctness remains a hard
precondition. Measurements from shared CI runners remain functional smoke data,
not authoritative evidence of relative performance.

## Decision

1. The official campaign format is `s3bench` schema version `1.0.0`.
2. Every case has a stable `benchmark_id`, an independently versioned
   `workload_version`, an input identifier, and an expected checksum.
3. A run proceeds through explicit discover, build, verify, warmup, calibrate,
   measure, summarize, export, compare, and report phases. A mode may omit an
   inapplicable phase only by recording it as unavailable, never as zero.
4. Build and link complete before correctness verification. Build failure,
   timeout, nonzero exit, missing checksum, truncated output, or checksum
   mismatch prevents measurement and ranking.
5. Warmups are discarded and never appear among measured samples.
6. Calibration is deterministic and bounded. It increases loops geometrically
   until the target sample duration is reached, subject to explicit maximum
   loops, attempts, and timeout limits. Calibration samples are not final
   samples.
7. The portable defaults are three warmups, fifteen measured samples, a
   200,000,000 ns target sample duration, a finite calibration-attempt limit,
   and an explicit per-command timeout. Smoke mode uses smaller values only to
   validate the machinery.
8. Durations use `time.perf_counter_ns()`, a monotonic high-resolution clock.
   Wall-clock timestamps are UTC metadata only and never measure duration.
9. Each measured sample records the raw duration in nanoseconds and the final
   loops-per-sample value. Raw samples are preserved in exported results.
10. Summaries contain median, arithmetic mean, minimum, maximum, sample standard
    deviation, coefficient of variation, and nearest-rank percentile 95. The
    median is the primary reported statistic.
11. Outliers are retained by default. High variability produces a warning and
    does not delete or rewrite samples.
12. Compile, link, process startup, kernel runtime, full process runtime,
    end-to-end duration, artifact size, and peak memory are distinct fields.
    Unsupported measurements are `null` with an explanatory note.
13. Startup and kernel timings are reported only when the implementation exposes
    a trustworthy boundary. Full-process timing must not be relabeled as kernel
    timing.
14. Every result records repository SHA and dirty state, operating system,
    architecture, CPU model when detectable, logical and physical CPU counts
    when detectable, total memory when detectable, Python version, runner type,
    toolchain name/version/flags, linker, artifact metadata, and UTC timestamp.
15. Metadata must not contain username, private hostname, home directory, local
    absolute paths, environment dumps, IP addresses, credentials, tokens, or
    unnecessary personal identifiers.
16. Commands are argument lists executed without a shell. Standard output,
    standard error, exit status, timeout state, and checksum are captured.
17. JSON and Markdown output ordering is deterministic. JSON forbids NaN and
    infinity. Large machine-specific raw results are ignored by default.
18. Baselines may be committed only from a clean, identified repository state
    after schema validation, checksum verification, complete execution,
    environment capture, and human report review.
19. `benchmarks/baseline-0.8-e2.json` is immutable historical evidence. The
    historical loader classifies each comparison as `COMPARABLE`,
    `PARTIALLY_COMPARABLE`, or `NOT_COMPARABLE`; missing protocol metadata
    prevents conclusive percentage claims.
20. S3 emulator, S3 native, and Python reference results are separate execution
    classes. Portable native tables do not mix interpreted results.
21. Cross-language comparisons require equivalent algorithm, input, checksum,
    timed region, and explicit optimization flags. S3 O0 is shown with C O0,
    Rust opt-level 0, and Zig Debug; S3 O1 is shown with C O2, Rust opt-level 2,
    and Zig ReleaseFast, without claiming optimizer equivalence.
22. Missing external toolchains are recorded as unavailable. The harness never
    installs a compiler, fabricates a result, substitutes another mode, or uses
    missing values as zero.
23. Shared CI runs schema, discovery, build, checksum, deterministic export, and
    short smoke execution. It has no absolute or percentage performance gate.
24. Authoritative native comparison requires one controlled Linux environment
    for S3 native O0/O1 and all selected external toolchains, with identical
    workload inputs and complete metadata.
25. A regression or improvement claim requires compatible workload and protocol,
    validated checksums, raw samples, environment evidence, and review. Minimum
    duration alone is never sufficient.
26. The current maturity is experimental engineering infrastructure. Python
    remains the default compiler frontend, the bounded S3 frontend remains a
    candidate, and public IR and Assembly remain version 0.6.0.

## Consequences

The new protocol can evolve beside the 0.8 runner while preserving the existing
deterministic baseline. Functional checks and smoke execution can run broadly,
but performance claims become deliberately narrower and require comparable,
reviewed evidence.

The infrastructure adds manifests, adapters, raw result handling, and report
generation. Some phases and memory metrics will remain unavailable on platforms
that cannot expose a trustworthy boundary. Those gaps are visible data rather
than implicit zeros.
