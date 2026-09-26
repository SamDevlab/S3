"""Measure equivalent native kernels in-process behind one scalar ABI."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from bootstrap.s3.backends.x86_64 import NativeToolchain, generate_ffi_assembly
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source


X, Y, Z = 1.125, -2.5, 3.25
DEFAULT_ITERATIONS = 1_000
DEFAULT_WARMUPS = 3
DEFAULT_SAMPLES = 21
BOOTSTRAP_SEED = 1401
BOOTSTRAP_REPLICATES = 5_000
MATERIALITY = 0.05

S3_SOURCE = """\
export fn kernel(x: f64, y: f64, z: f64, iterations: i64) -> f64:
    mut iteration: i64 = 0
    mut total: f64 = 0.0
    while iteration < iterations:
        total = total + x * x + y * y + z * z
        iteration = iteration + 1
    return total
fn main() -> i64:
    return 0
"""

C_SOURCE = """\
#include <stdint.h>
double kernel(double x, double y, double z, int64_t iterations) {
    int64_t iteration = 0;
    double total = 0.0;
    while (iteration < iterations) {
        total = total + x * x + y * y + z * z;
        iteration = iteration + 1;
    }
    return total;
}
"""

RUST_SOURCE = """\
#[no_mangle]
pub extern "C" fn kernel(x: f64, y: f64, z: f64, iterations: i64) -> f64 {
    let mut iteration: i64 = 0;
    let mut total: f64 = 0.0;
    while iteration < iterations {
        total = total + x * x + y * y + z * z;
        iteration = iteration + 1;
    }
    total
}
"""

ZIG_SOURCE = """\
export fn kernel(x: f64, y: f64, z: f64, iterations: i64) f64 {
    var iteration: i64 = 0;
    var total: f64 = 0.0;
    while (iteration < iterations) : (iteration += 1) {
        total = total + x * x + y * y + z * z;
    }
    return total;
}
"""


def expected_result(iterations: int) -> float:
    total = 0.0
    contribution = X * X + Y * Y + Z * Z
    for _ in range(iterations):
        total = total + contribution
    return total


def summarize(samples: list[int]) -> dict[str, float | int]:
    if len(samples) < 3 or any(value <= 0 for value in samples):
        raise ValueError("at least three positive timing samples are required")
    ordered = sorted(samples)
    mean = statistics.fmean(ordered)
    return {
        "sample_count": len(ordered),
        "median_ns": statistics.median(ordered),
        "p95_ns": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "coefficient_of_variation": statistics.stdev(ordered) / mean if mean else 0.0,
        "minimum_ns": ordered[0],
        "maximum_ns": ordered[-1],
    }


def classify_paired_speedup(
    reference_samples: list[int],
    candidate_samples: list[int],
    *,
    seed: int = BOOTSTRAP_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, object]:
    if len(reference_samples) != len(candidate_samples) or len(reference_samples) < 3:
        raise ValueError("paired samples must have the same length and contain at least three pairs")
    ratios = [reference / candidate for reference, candidate in zip(reference_samples, candidate_samples, strict=True)]
    point = statistics.median(ratios)
    randomizer = random.Random(seed)
    medians = sorted(
        statistics.median(randomizer.choices(ratios, k=len(ratios)))
        for _ in range(replicates)
    )
    low = medians[math.floor(0.025 * replicates)]
    high = medians[min(replicates - 1, math.ceil(0.975 * replicates) - 1)]
    if low > 1.0 + MATERIALITY:
        classification = "IMPROVEMENT"
    elif high < 1.0 - MATERIALITY:
        classification = "REGRESSION"
    elif low >= 1.0 - MATERIALITY and high <= 1.0 + MATERIALITY:
        classification = "NEUTRAL"
    else:
        classification = "INDETERMINATE"
    return {
        "speedup_reference_over_candidate_median": point,
        "paired_bootstrap_95_percent_interval": [low, high],
        "materiality_threshold_percent": MATERIALITY * 100,
        "classification": classification,
        "bootstrap_seed": seed,
        "bootstrap_replicates": replicates,
    }


def _run(arguments: list[str], *, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
    )


def _git_revision_and_clean_tree() -> str:
    revision = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
    status = _run(["git", "status", "--porcelain"]).stdout
    if status:
        raise RuntimeError("benchmark requires a clean, frozen source worktree")
    return revision


def _compiler_version(command: str, args: tuple[str, ...]) -> str:
    result = _run([command, *args])
    return (result.stdout.strip() or result.stderr.strip()).splitlines()[0]


def _section_sizes(path: Path) -> dict[str, int]:
    result = _run(["size", "-A", str(path)])
    sections: dict[str, int] = {}
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) >= 2 and columns[0].startswith("."):
            try:
                sections[columns[0]] = int(columns[1])
            except ValueError:
                continue
    return sections


def _measure(function, iterations: int) -> tuple[int, float]:
    started = time.perf_counter_ns()
    result = function(X, Y, Z, iterations)
    return time.perf_counter_ns() - started, float(result)


def run_benchmark(
    output: Path,
    *,
    iterations: int = DEFAULT_ITERATIONS,
    warmups: int = DEFAULT_WARMUPS,
    samples: int = DEFAULT_SAMPLES,
) -> dict[str, object]:
    started_at_utc = datetime.now(timezone.utc).isoformat()
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("kernel-scope native benchmark requires Linux x86-64")
    if iterations < 1 or warmups < 1 or samples < 3:
        raise ValueError("iterations and warmups must be positive and samples must be >= 3")
    revision = _git_revision_and_clean_tree()
    cc = shutil.which("cc")
    rustc = shutil.which("rustc")
    size = shutil.which("size")
    if cc is None or rustc is None or size is None:
        raise RuntimeError("kernel-scope benchmark requires cc, rustc, and binutils size")
    zig = shutil.which("zig")
    output.mkdir(parents=True, exist_ok=True)
    sources = {
        "s3": S3_SOURCE,
        "c": C_SOURCE,
        "rust": RUST_SOURCE,
    }
    if zig is not None:
        sources["zig"] = ZIG_SOURCE
    artifacts: dict[str, Path] = {}
    build_metadata: dict[str, object] = {}
    expected = expected_result(iterations)

    s3_path = output / "libs3_kernel.so"
    s3_assembly = output / "s3_kernel.s"
    started = time.perf_counter_ns()
    s3_compilation = compile_source(S3_SOURCE, optimization=OptimizationLevel.O1)
    _, s3_ordinary_assembly = s3_compilation.require_ordinary_artifacts()
    s3_native_assembly = generate_ffi_assembly(s3_ordinary_assembly)
    s3_toolchain = NativeToolchain.detect()
    s3_toolchain.build_shared(s3_native_assembly, s3_path, keep_assembly=s3_assembly)
    build_metadata["s3"] = {
        "build_duration_ns": time.perf_counter_ns() - started,
        "compiler": s3_toolchain.compiler,
        "compiler_version": _compiler_version(s3_toolchain.compiler, ("--version",)),
        "s3_compiler": "Python reference compiler",
        "optimization": OptimizationLevel.O1.value,
        "source_sha256": hashlib.sha256(S3_SOURCE.encode()).hexdigest(),
        "source_bytes": len(S3_SOURCE.encode()),
        "assembly_bytes": s3_assembly.stat().st_size,
        "flags": [OptimizationLevel.O1.value, "x86-64 FFI shared-library mode"],
    }
    artifacts["s3"] = s3_path

    c_source = output / "kernel.c"
    c_source.write_text(C_SOURCE, encoding="utf-8", newline="\n")
    c_path = output / "libc_kernel.so"
    c_flags = ["-O1", "-fno-fast-math", "-ffp-contract=off", "-fPIC", "-shared"]
    started = time.perf_counter_ns()
    _run([cc, *c_flags, str(c_source), "-o", str(c_path)])
    build_metadata["c"] = {
        "build_duration_ns": time.perf_counter_ns() - started,
        "compiler": cc,
        "compiler_version": _compiler_version(cc, ("--version",)),
        "optimization": "-O1",
        "source_sha256": hashlib.sha256(C_SOURCE.encode()).hexdigest(),
        "source_bytes": len(C_SOURCE.encode()),
        "flags": c_flags,
    }
    artifacts["c"] = c_path

    rust_source = output / "kernel.rs"
    rust_source.write_text(RUST_SOURCE, encoding="utf-8", newline="\n")
    rust_path = output / "librust_kernel.so"
    rust_flags = ["--crate-type", "cdylib", "--edition=2021", "-C", "opt-level=1", "-C", "overflow-checks=yes"]
    started = time.perf_counter_ns()
    _run([rustc, *rust_flags, str(rust_source), "-o", str(rust_path)])
    build_metadata["rust"] = {
        "build_duration_ns": time.perf_counter_ns() - started,
        "compiler": rustc,
        "compiler_version": _compiler_version(rustc, ("--version",)),
        "optimization": "opt-level=1",
        "source_sha256": hashlib.sha256(RUST_SOURCE.encode()).hexdigest(),
        "source_bytes": len(RUST_SOURCE.encode()),
        "flags": rust_flags,
    }
    artifacts["rust"] = rust_path

    if zig is not None:
        zig_source = output / "kernel.zig"
        zig_source.write_text(ZIG_SOURCE, encoding="utf-8", newline="\n")
        zig_path = output / "libzig_kernel.so"
        zig_flags = ["build-lib", str(zig_source), "-dynamic", "-O", "ReleaseSafe", "-femit-bin=" + str(zig_path)]
        started = time.perf_counter_ns()
        _run([zig, *zig_flags])
        build_metadata["zig"] = {
            "build_duration_ns": time.perf_counter_ns() - started,
            "compiler": zig,
            "compiler_version": _compiler_version(zig, ("version",)),
            "optimization": "ReleaseSafe",
            "source_sha256": hashlib.sha256(ZIG_SOURCE.encode()).hexdigest(),
            "source_bytes": len(ZIG_SOURCE.encode()),
            "flags": zig_flags,
        }
        artifacts["zig"] = zig_path

    libraries = {name: ctypes.CDLL(str(path)) for name, path in artifacts.items()}
    functions = {}
    for name, library in libraries.items():
        function = getattr(library, "kernel")
        function.argtypes = [
            ctypes.c_double,
            ctypes.c_double,
            ctypes.c_double,
            ctypes.c_int64,
        ]
        function.restype = ctypes.c_double
        functions[name] = function
    for name, function in functions.items():
        _, checksum = _measure(function, iterations)
        if checksum != expected:
            raise RuntimeError(f"{name} checksum mismatch: got {checksum!r}, expected {expected!r}")

    for _ in range(warmups):
        for name in functions:
            _, checksum = _measure(functions[name], iterations)
            if checksum != expected:
                raise RuntimeError(f"{name} warmup checksum mismatch")

    timings = {name: [] for name in functions}
    names = tuple(functions)
    for sample_index in range(samples):
        start_index = sample_index % len(names)
        order = names[start_index:] + names[:start_index]
        for name in order:
            elapsed, checksum = _measure(functions[name], iterations)
            if checksum != expected:
                raise RuntimeError(f"{name} timed checksum mismatch")
            timings[name].append(elapsed)

    per_implementation: dict[str, object] = {}
    for name, path in artifacts.items():
        sections = _section_sizes(path)
        per_implementation[name] = {
            "measurement_scope": "kernel",
            "process_launches_in_timed_region": 0,
            "warmups": warmups,
            "timings": summarize(timings[name]),
            "checksum": expected,
            "checksum_matches_reference": True,
            "artifact_bytes": path.stat().st_size,
            "assembly_source_bytes": build_metadata[name].get("assembly_bytes"),
            "section_bytes": sections,
            "text_bytes": sections.get(".text"),
            "rodata_bytes": sections.get(".rodata"),
        }

    comparisons = {
        name: classify_paired_speedup(timings[name], timings["s3"])
        for name in names
        if name != "s3"
    }
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
    result: dict[str, object] = {
        "schema_version": "1.0.0",
        "benchmark_id": "geometry.point-radius-reduction.native-kernel.v1",
        "source_head": revision,
        "campaign_tree_clean": True,
        "started_at_utc": started_at_utc,
        "architecture": platform.machine(),
        "os": platform.platform(),
        "cpu_model": _cpu_model(),
        "cpu_affinity": affinity,
        "dataset": {"identity": "one immutable point (1.125,-2.5,3.25)", "point_count": 1},
        "kernel": "repeat squared-radius accumulation in the same left-to-right order",
        "kernel_iterations": iterations,
        "elements_processed_per_sample": iterations,
        "timing_scope": "one in-process C ABI kernel call; build/load/setup outside timer",
        "ffi_call_included": True,
        "startup_in_timed_region": False,
        "warmups": warmups,
        "paired_samples": samples,
        "sample_order": "rotating implementation order by sample index",
        "optimization_policy": "S3 O1; C -O1 strict FP; Rust opt-level=1 strict FP; Zig ReleaseSafe if installed",
        "python_version": platform.python_version(),
        "native_speedup_claim": False,
        "comparison_method": {
            "paired_ratio": "reference_duration / S3_duration",
            "classification": "paired bootstrap median interval with predeclared 5% materiality threshold",
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        },
        "expected_checksum": expected,
        "builds": build_metadata,
        "implementations": per_implementation,
        "comparisons_to_s3": comparisons,
        "zig_status": "MEASURED" if zig is not None else "TOOLCHAIN_UNAVAILABLE",
    }
    output_file = output / "native-kernel-scope.json"
    output_file.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unavailable"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    args = parser.parse_args()
    result = run_benchmark(
        args.output,
        iterations=args.iterations,
        warmups=args.warmups,
        samples=args.samples,
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
