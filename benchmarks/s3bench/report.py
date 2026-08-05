"""Deterministic comparative report rendering for s3bench results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

# _canonical_reference lives in core.py as the single source of truth;
# normalized_rows imports it so the two code paths can never diverge
# on the reference choice.
from .core import _canonical_reference, duration_per_loop_ns

UNOPTIMIZED_MODES = {"O0", "opt-level=0", "Debug"}
OPTIMIZED_MODES = {"O1", "O2", "opt-level=2", "ReleaseFast"}


def comparison_tables(
    results: Sequence[Mapping[str, object]],
) -> dict[str, list[Mapping[str, object]]]:
    measured = [item for item in results if item.get("status") == "measured"]
    portable_native = [
        item
        for item in measured
        if item.get("suite") == "portable" and item.get("execution_mode") == "native"
    ]
    return {
        "unoptimized": _ordered(
            item for item in portable_native if item.get("optimization_mode") in UNOPTIMIZED_MODES
        ),
        "optimized": _ordered(
            item for item in portable_native if item.get("optimization_mode") in OPTIMIZED_MODES
        ),
        "emulated": _ordered(
            item
            for item in measured
            if item.get("suite") == "portable" and item.get("execution_mode") == "emulator"
        ),
        "interpreted": _ordered(
            item
            for item in measured
            if item.get("suite") == "portable" and item.get("execution_mode") == "interpreted"
        ),
        "s3_specific": _ordered(item for item in measured if item.get("suite") == "s3-specific"),
        "unavailable": _ordered(item for item in results if item.get("status") in {"unavailable", "failed"}),
    }


def normalized_rows(
    results: Sequence[Mapping[str, object]],
    *,
    reference_implementation: str = "c",
    reference_optimization: str = "O2",
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    # Scope-aware grouping: NEVER normalize across measurement_scope.
    # A kernel reference (C O2, loops>>1) cannot serve a process result
    # (S3 native, loops=1, includes fork/exec/ELF load) and vice versa.
    by_scope: dict[tuple[str, str, str, str], list[Mapping[str, object]]] = {}
    for result in results:
        key = (
            str(result.get("benchmark_id", "")),
            str(result.get("input_id", "")),
            str(result.get("measurement_scope", "")),
            str(result.get("phase", "")),
        )
        by_scope.setdefault(key, []).append(result)
    for scope_key in sorted(by_scope):
        group = by_scope[scope_key]
        # ONE canonical reference per group — deterministic, non-circular.
        canonical = _canonical_reference(
            group,
            reference_implementation=reference_implementation,
            reference_optimization=reference_optimization,
        )
        canonical_per_loop = duration_per_loop_ns(canonical) if canonical else None
        canonical_mode = canonical.get("execution_mode") if canonical else None
        canonical_opt = canonical.get("optimization_mode") if canonical else None
        canonical_scope = canonical.get("measurement_scope") if canonical else None
        canonical_impl = canonical.get("implementation") if canonical else None
        for item in _ordered(group):
            median = item.get("median_ns")
            median_per_loop = duration_per_loop_ns(item)
            ratio = None
            reference_impl: str | None = None
            if (
                canonical is not None
                and canonical_scope == item.get("measurement_scope")
                and item.get("status") == "measured"
                and item.get("comparability_classification") == "COMPARABLE"
                and median_per_loop is not None
                and canonical_per_loop is not None
                and canonical_per_loop > 0
            ):
                ratio = median_per_loop / canonical_per_loop
                reference_impl = str(canonical_impl)
            rows.append(
                {
                    "benchmark_id": scope_key[0],
                    "input_id": scope_key[1],
                    "measurement_scope": item.get("measurement_scope"),
                    "phase": scope_key[3],
                    "implementation": item.get("implementation"),
                    "execution_mode": item.get("execution_mode"),
                    "optimization_mode": item.get("optimization_mode"),
                    "process_launches_per_sample": item.get("process_launches_per_sample"),
                    "median_ns": median,
                    "median_ns_per_loop": median_per_loop,
                    "loops_per_sample": item.get("loops_per_sample"),
                    "reference_implementation": reference_impl,
                    "reference_execution_mode": canonical_mode,
                    "reference_optimization_mode": canonical_opt,
                    "reference_measurement_scope": canonical_scope,
                    "normalized_ratio": ratio,
                    "comparability_classification": item.get("comparability_classification"),
                }
            )
    return rows


def render_performance_report(
    results: Sequence[Mapping[str, object]],
    *,
    raw_result_path: str,
) -> str:
    tables = comparison_tables(results)
    repository_sha = _first_value(results, "repository_sha")
    operating_system = _first_value(results, "operating_system")
    architecture = _first_value(results, "architecture")
    runner_type = _first_value(results, "runner_type")
    recommendations = _recommendations(results)
    # Methodology: split results by measurement_scope so that kernel
    # timing (internal loop, loops>>1) is never presented alongside
    # process/startup timing (one fork/exec per sample, loops=1) in a
    # single comparable table. The two are different physical quantities.
    kernel_results = [r for r in results if r.get("measurement_scope") == "kernel"]
    process_results = [r for r in results if r.get("measurement_scope") == "process"]
    lines = [
        "# S3 Performance Report 1.19",
        "",
        "## Scope",
        "",
        "Portable S3, C, Rust, and Zig workloads are separate from S3-specific engineering cases.",
        "",
        "## Repository SHA",
        "",
        str(repository_sha),
        "",
        "## Benchmark schema",
        "",
        "s3bench 1.0.0",
        "",
        "## Hardware",
        "",
        f"Architecture: {architecture}. Detailed CPU and memory metadata remain in raw JSON.",
        "",
        "## Operating system",
        "",
        f"{operating_system}; runner classification: {runner_type}.",
        "",
        "## Toolchains",
        "",
        _toolchain_summary(results),
        "",
        "## Power and background-load conditions",
        "",
        "Not automatically controlled; authoritative runs require operator documentation.",
        "",
        "## Methodology",
        "",
        "Build, correctness, warmup, calibration, final samples, summary, export, and comparison are separate phases.",
        "",
        "## Measurement scope",
        "",
        "Results are partitioned by measurement_scope. KERNEL MEASUREMENTS run an internal loop with loops_per_sample > 1; median_ns_per_loop is a kernel-region cost. PROCESS/STARTUP MEASUREMENTS launch one process per sample with loops_per_sample = 1; median_ns_per_loop is the duration per process/sample and is NOT a kernel cost.",
        "",
        "## Warmups",
        "",
        str(_first_value(results, "warmup_count")),
        "",
        "## Calibration",
        "",
        "Bounded geometric calibration targets the configured sample duration; calibration samples are discarded.",
        "",
        "## Samples",
        "",
        str(_first_value(results, "sample_count")),
        "",
        "## Statistics",
        "",
        "Median is primary; mean, min, max, sample standard deviation, CV, and nearest-rank p95 are retained.",
        "",
        "## Correctness verification",
        "",
        "Only checksum-verified cases are measured and eligible for comparison.",
        "",
        "## Timed regions",
        "",
        "Compile, link, full process, startup, kernel, end-to-end, size, and memory remain distinct fields.",
        "",
        "## KERNEL MEASUREMENTS",
        "",
        "_Kernel-scoped adapters run an internal loop with loops_per_sample > 1. median_ns_per_loop is comparable across kernel implementations only._",
        "",
        _kernel_table(kernel_results, _registry(tables, kernel_results)),
        "",
        "## PROCESS/STARTUP MEASUREMENTS",
        "",
        "_Process-scoped adapters launch one process per sample with loops_per_sample = 1; median_ns_per_loop is the duration per process/sample, NOT a kernel cost. S3 native O0 and O1 may be compared within this scope only._",
        "",
        _process_table(process_results, _registry(tables, process_results)),
        "",
        "## Portable suite (legacy view)",
        "",
        _table(tables["optimized"] + tables["unoptimized"]),
        "",
        "## S3-specific suite",
        "",
        _table(tables["s3_specific"]),
        "",
        "## S3 emulator",
        "",
        _table(tables["emulated"]),
        "",
        "## Interpreted reference",
        "",
        _table(tables["interpreted"]),
        "",
        "## Compiler pipeline",
        "",
        _table(item for item in tables["s3_specific"] if item.get("category") == "compiler-pipeline"),
        "",
        "## Emulator versus native",
        "",
        _table(item for item in results if item.get("implementation") == "s3"),
        "",
        "## O0 versus O1",
        "",
        _table(item for item in results if item.get("implementation") == "s3" and item.get("optimization_mode") in {"O0", "O1"}),
        "",
        "## Historical baseline",
        "",
        "The 0.8 E2 baseline is historical and NOT COMPARABLE for timing by default.",
        "",
        "## C comparison",
        "",
        _table(item for item in results if item.get("implementation") == "c"),
        "",
        "## Rust comparison",
        "",
        _table(item for item in results if item.get("implementation") == "rust"),
        "",
        "## Zig comparison",
        "",
        _table(item for item in results if item.get("implementation") == "zig"),
        "",
        "## Artifact sizes",
        "",
        _artifact_table(results),
        "",
        "## Variability",
        "",
        _variability_summary(results),
        "",
        "## Non-comparable results",
        "",
        _table(item for item in results if item.get("comparability_classification") != "COMPARABLE"),
        "",
        "## Regressions",
        "",
        "No claim without a compatible reviewed baseline.",
        "",
        "## Improvements",
        "",
        "No claim without a compatible reviewed baseline.",
        "",
        "## Known limitations",
        "",
        "Shared CI is non-authoritative; missing toolchains and incompatible timed regions remain explicit. Process/startup timing is never normalized against kernel timing.",
        "",
        "## Reproduction commands",
        "",
        "`python tools/s3bench.py --verify-only`",
        "",
        "`python tools/s3bench.py --output-json benchmarks/results/result.json --output-markdown benchmarks/results/report.md`",
        "",
        "## Raw result locations",
        "",
        raw_result_path,
        "",
        "## Recommended optimization priorities",
        "",
        recommendations,
        "",
    ]
    return "\n".join(lines)


def _registry(tables, results):
    """Constrain the legacy comparison_tables buckets to a scope subset."""
    wanted = {id(r) for r in results}
    return {key: [r for r in bucket if id(r) in wanted] for key, bucket in tables.items()}


def _kernel_table(results, registry) -> str:
    rows = _ordered(results)
    lines = [
        "| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    if not rows:
        lines.append("| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |")
    for item in rows:
        lines.append(
            f"| {item.get('benchmark_id')} | {item.get('implementation')} | "
            f"{item.get('execution_mode')} | {item.get('optimization_mode')} | "
            f"{_value(item.get('median_ns'))} | {_value(item.get('loops_per_sample'))} | "
            f"{_value(duration_per_loop_ns(item))} | {_value(item.get('coefficient_of_variation'))} | "
            f"{item.get('status')} | {item.get('comparability_classification')} |"
        )
    return "\n".join(lines)


def _process_table(results, registry) -> str:
    # Process/startup scope: loops_per_sample is always 1. The
    # "Median ns/loop" column is physically a per-process/per-sample
    # duration; we relabel it to avoid implying a kernel cost.
    rows = _ordered(results)
    lines = [
        "| Benchmark | Implementation | Mode | Optimization | Median ns/process | Loops/process | Median ns/process | CV | Status | Comparability |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    if not rows:
        lines.append("| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |")
    for item in rows:
        lines.append(
            f"| {item.get('benchmark_id')} | {item.get('implementation')} | "
            f"{item.get('execution_mode')} | {item.get('optimization_mode')} | "
            f"{_value(item.get('median_ns'))} | {_value(item.get('loops_per_sample'))} | "
            f"{_value(duration_per_loop_ns(item))} | {_value(item.get('coefficient_of_variation'))} | "
            f"{item.get('status')} | {item.get('comparability_classification')} |"
        )
    return "\n".join(lines)


def _ordered(results):
    return sorted(
        results,
        key=lambda item: (
            str(item.get("benchmark_id", "")),
            str(item.get("implementation", "")),
            str(item.get("execution_mode", "")),
            str(item.get("optimization_mode", "")),
        ),
    )


def _table(results) -> str:
    rows = _ordered(results)
    lines = [
        "| Benchmark | Implementation | Mode | Optimization | Median ns/sample | Loops | Median ns/loop | CV | Status | Comparability |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    if not rows:
        lines.append("| unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | NOT_COMPARABLE |")
    for item in rows:
        lines.append(
            f"| {item.get('benchmark_id')} | {item.get('implementation')} | "
            f"{item.get('execution_mode')} | {item.get('optimization_mode')} | "
            f"{_value(item.get('median_ns'))} | {_value(item.get('loops_per_sample'))} | "
            f"{_value(duration_per_loop_ns(item))} | {_value(item.get('coefficient_of_variation'))} | "
            f"{item.get('status')} | {item.get('comparability_classification')} |"
        )
    return "\n".join(lines)


def _artifact_table(results: Sequence[Mapping[str, object]]) -> str:
    lines = ["| Benchmark | Implementation | Artifact bytes |", "| --- | --- | ---: |"]
    rows = _ordered(results)
    if not rows:
        lines.append("| unavailable | unavailable | unavailable |")
    for item in rows:
        lines.append(
            f"| {item.get('benchmark_id')} | {item.get('implementation')} | "
            f"{_value(item.get('artifact_size_bytes'))} |"
        )
    return "\n".join(lines)


def _toolchain_summary(results: Sequence[Mapping[str, object]]) -> str:
    values = sorted({
        f"{item.get('compiler_name')}: {item.get('compiler_version')} ({' '.join(item.get('compiler_flags', []))})"
        for item in results if item.get("compiler_name")
    })
    return "; ".join(values) if values else "unavailable"


def _variability_summary(results: Sequence[Mapping[str, object]]) -> str:
    high = [item for item in results if isinstance(item.get("coefficient_of_variation"), (int, float)) and item["coefficient_of_variation"] > 0.10]
    return f"{len(high)} measured cases have CV above 0.10; all raw samples are preserved."


def _recommendations(results: Sequence[Mapping[str, object]]) -> str:
    comparable = [
        item for item in results
        if item.get("status") == "measured"
        and item.get("implementation") == "s3"
        and item.get("comparability_classification") == "COMPARABLE"
        and duration_per_loop_ns(item) is not None
    ]
    if not comparable:
        return "Pending validated comparable measurements."
    slowest = max(comparable, key=lambda item: duration_per_loop_ns(item) or 0.0)
    return f"Review `{slowest.get('benchmark_id')}` first; it has the largest comparable median cost per loop in this result set."


def _first_value(results: Sequence[Mapping[str, object]], key: str) -> object:
    return next((item.get(key) for item in results if item.get(key) is not None), "unavailable")


def _value(value: object) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)
