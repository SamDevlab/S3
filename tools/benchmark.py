#!/usr/bin/env python3
"""In-process benchmark runner for S3."""

import argparse
import datetime
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import time
import hashlib
from pathlib import Path

# Direct imports - no ImportError hiding
from bootstrap.s3 import OptimizationLevel, compile_source, run_source
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.assembly import ASSEMBLY_FORMAT_VERSION
from bootstrap.s3.backends.x86_64.backend import generate_native_assembly
from bootstrap.s3.diagnostics import DIAGNOSTIC_SCHEMA_VERSION
from bootstrap.s3.ir_serialization import IR_FORMAT_VERSION

BENCHMARK_FORMAT_VERSION = "1.0.0"

def get_distribution_version() -> str:
    try:
        return importlib.metadata.version("s3-bootstrap")
    except importlib.metadata.PackageNotFoundError:
        return "0.7.0"  # fallback if not installed as a package, though it should be

def syntax_mode_to_string(mode: SyntaxMode) -> str:
    if mode == SyntaxMode.V0_5:
        return "0.5"
    if mode == SyntaxMode.V0_6:
        return "0.6"
    return str(mode)

def get_git_commit() -> str:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        return commit if commit else "unavailable"
    except Exception:
        return "unavailable"

def is_git_dirty() -> str:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            stderr=subprocess.DEVNULL
        ).strip()
        return "true" if out else "false"
    except Exception:
        return "unknown"

def sanitize_processor(proc: str) -> str:
    return proc.strip()

def gather_metadata(args, workloads_order: list[str]) -> dict:
    return {
        "benchmark_format_version": BENCHMARK_FORMAT_VERSION,
        "commit": get_git_commit(),
        "dirty": is_git_dirty(),
        "distribution": get_distribution_version(),
        "source_syntax": syntax_mode_to_string(SyntaxMode.V0_6),
        "ir_version": IR_FORMAT_VERSION,
        "assembly_version": ASSEMBLY_FORMAT_VERSION,
        "diagnostic_schema": DIAGNOSTIC_SCHEMA_VERSION,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "os": platform.system(),
        "architecture": platform.machine(),
        "processor": sanitize_processor(platform.processor()),
        "logical_cpus": os.cpu_count() or 1,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "mode": args.mode,
        "optimization": args.optimization,
        "warmups": args.warmups,
        "runs": args.runs,
        "workloads_order": workloads_order,
    }

def calc_min(samples: list[int]) -> int:
    if not samples:
        raise ValueError("Empty collection")
    return min(samples)

def calc_max(samples: list[int]) -> int:
    if not samples:
        raise ValueError("Empty collection")
    return max(samples)

def calc_mean(samples: list[int]) -> float:
    if not samples:
        raise ValueError("Empty collection")
    mean_val = sum(samples) / len(samples)
    if math.isnan(mean_val) or math.isinf(mean_val):
        raise ValueError("Invalid mean")
    return mean_val

def calc_median(samples: list[int]) -> float:
    if not samples:
        raise ValueError("Empty collection")
    s = sorted(samples)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2.0
    return float(s[mid])

def calc_p95(samples: list[int]) -> int:
    if not samples:
        raise ValueError("Empty collection")
    s = sorted(samples)
    rank = math.ceil(0.95 * len(s))
    return s[rank - 1]

def load_manifest(manifest_path: Path) -> dict:
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def run_hosted_pipeline(source: str, opt: OptimizationLevel, max_inst: int, max_frames: int | None) -> int:
    kwargs = {"max_instructions": max_inst}
    if max_frames is not None:
        kwargs["max_frames"] = max_frames
    return run_source(source, optimization=opt, **kwargs)

def run_native_asm_pipeline(source: str, opt: OptimizationLevel, max_inst: int, max_frames: int | None) -> str:
    compilation = compile_source(source, optimization=opt)
    kwargs = {"max_instructions": max_inst}
    if max_frames is not None:
        kwargs["max_frames"] = max_frames
    return generate_native_assembly(compilation.assembly, **kwargs)

def exit_error(args, code: str, message: str, print_to_stderr=True):
    if args.format == "json":
        err_obj = {
            "benchmark_format_version": BENCHMARK_FORMAT_VERSION,
            "status": "error",
            "error": {
                "code": code,
                "message": message
            }
        }
        out_str = json.dumps(err_obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            try:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(out_str)
            except Exception:
                sys.exit(1)
        else:
            print(out_str, end="")
    else:
        if print_to_stderr:
            print(f"Error ({code}): {message}", file=sys.stderr)
    sys.exit(1)

def parse_args():
    parser = argparse.ArgumentParser(description="In-process benchmark runner for S3")
    parser.add_argument("--list", action="store_true", help="List available workloads")
    parser.add_argument("--mode", choices=["hosted-pipeline", "native-asm-pipeline"], help="Benchmark mode")
    parser.add_argument("--optimization", choices=["O0", "O1"], help="Optimization level")
    parser.add_argument("--workload", help="Workload ID or 'all'")
    parser.add_argument("--warmups", type=int, default=3, help="Number of warmups")
    parser.add_argument("--runs", type=int, default=10, help="Number of measured runs")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--include-samples", action="store_true", help="Include raw samples in JSON output")
    return parser.parse_args()

def main():
    try:
        args = parse_args()
    except SystemExit:
        # argparse handles its own exits; let it do so.
        raise

    root_dir = Path(__file__).resolve().parent.parent
    manifest_path = root_dir / "benchmarks" / "manifest.json"

    if not manifest_path.exists():
        exit_error(args, "S3_BENCH_INVALID_MANIFEST", f"Manifest not found: {manifest_path}")

    try:
        manifest = load_manifest(manifest_path)
    except Exception as e:
        exit_error(args, "S3_BENCH_INVALID_MANIFEST", f"Invalid manifest: {e}")

    workloads = manifest.get("workloads", [])

    if args.list:
        if args.format == "json":
            # For list, just print IDs in json or text
            pass
        for w in workloads:
            print(w["id"])
        sys.exit(0)

    if args.warmups is None or args.warmups < 0:
        exit_error(args, "S3_BENCH_INVALID_ARGUMENT", "Warmups must be >= 0")

    if args.runs is None or args.runs <= 0:
        exit_error(args, "S3_BENCH_INVALID_ARGUMENT", "Runs must be > 0")

    if not args.mode or not args.optimization or not args.workload:
        exit_error(args, "S3_BENCH_INVALID_ARGUMENT", "Missing required arguments for benchmarking.")

    opt_level = OptimizationLevel.O1 if args.optimization == "O1" else OptimizationLevel.O0

    if args.workload == "all":
        selected_workloads = workloads
    else:
        selected_workloads = [w for w in workloads if w["id"] == args.workload]
        if not selected_workloads:
            exit_error(args, "S3_BENCH_UNKNOWN_WORKLOAD", f"Unknown workload: {args.workload}")

    workloads_order = [w["id"] for w in selected_workloads]
    metadata = gather_metadata(args, workloads_order)

    results = []

    for w in selected_workloads:
        w_path = root_dir / "benchmarks" / w["file"]
        try:
            with w_path.open("r", encoding="utf-8") as f:
                source = f.read()
        except Exception as e:
            exit_error(args, "S3_BENCH_INVALID_MANIFEST", f"Failed to read workload source: {e}")

        expected_ret = w["expected_return"]
        max_inst = w["max_instructions"]
        max_frames = w.get("max_frames")

        # Native ASM Determinism Check
        if args.mode == "native-asm-pipeline":
            try:
                out1 = run_native_asm_pipeline(source, opt_level, max_inst, max_frames)
                out2 = run_native_asm_pipeline(source, opt_level, max_inst, max_frames)
            except Exception as e:
                exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Workload {w['id']} failed during determinism check: {e}")

            if not out1 or not out2:
                exit_error(args, "S3_BENCH_NATIVE_EMPTY", f"Workload {w['id']} generated empty output")
            if out1 != out2:
                exit_error(args, "S3_BENCH_NATIVE_NON_DETERMINISTIC", f"Workload {w['id']} native asm output is non-deterministic")

            artifact_size = len(out1.encode("utf-8"))
            artifact_sha256 = hashlib.sha256(out1.encode("utf-8")).hexdigest()

        # Validation run (functional validation)
        try:
            if args.mode == "hosted-pipeline":
                actual = run_hosted_pipeline(source, opt_level, max_inst, max_frames)
                if actual != expected_ret:
                    exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Workload {w['id']} failed: expected {expected_ret}, got {actual}")
        except Exception as e:
            exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Workload {w['id']} failed with exception: {e}")

        # Warmups
        for _ in range(args.warmups):
            if args.mode == "hosted-pipeline":
                actual = run_hosted_pipeline(source, opt_level, max_inst, max_frames)
                if actual != expected_ret:
                    exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Warmup failed for {w['id']}")
            else:
                out = run_native_asm_pipeline(source, opt_level, max_inst, max_frames)
                if not out:
                    exit_error(args, "S3_BENCH_NATIVE_EMPTY", f"Warmup failed for {w['id']}: empty output")

        # Runs
        samples = []
        actual_for_json = None
        for _ in range(args.runs):
            if args.mode == "hosted-pipeline":
                start_ns = time.perf_counter_ns()
                actual = run_hosted_pipeline(source, opt_level, max_inst, max_frames)
                end_ns = time.perf_counter_ns()

                if actual != expected_ret:
                    exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Run failed for {w['id']}")
                actual_for_json = actual
            else:
                start_ns = time.perf_counter_ns()
                out = run_native_asm_pipeline(source, opt_level, max_inst, max_frames)
                end_ns = time.perf_counter_ns()

                if not out:
                    exit_error(args, "S3_BENCH_NATIVE_EMPTY", f"Run failed for {w['id']}: empty output")

            samples.append(end_ns - start_ns)

        res = {
            "workload": w["id"],
            "status": "passed",
            "expected_return": expected_ret,
            "max_instructions": max_inst,
            "max_frames": max_frames,
            "statistics": {
                "unit": "ns",
                "minimum": calc_min(samples),
                "maximum": calc_max(samples),
                "mean": calc_mean(samples),
                "median": calc_median(samples),
                "p95": calc_p95(samples),
            }
        }

        if args.mode == "hosted-pipeline":
            res["actual_return"] = actual_for_json
        else:
            # For native asm, we don't execute it, so no actual_return.
            # We record artifact info instead.
            res["artifact_kind"] = "gnu-x86-64-assembly"
            res["artifact_size_bytes"] = artifact_size
            res["artifact_sha256"] = artifact_sha256

        if args.include_samples:
            res["samples_ns"] = samples

        results.append(res)

    output_data = {
        "benchmark_format_version": BENCHMARK_FORMAT_VERSION,
        "metadata": metadata,
        "configuration": {
            "mode": args.mode,
            "optimization": args.optimization,
            "warmups": args.warmups,
            "runs": args.runs,
            "include_samples": args.include_samples
        },
        "results": results
    }

    if args.format == "json":
        out_str = json.dumps(output_data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    else:
        lines = []
        for r in results:
            lines.append(f"Workload: {r['workload']}")
            s = r["statistics"]
            lines.append(f"  Min:    {s['minimum'] / 1_000_000.0:.3f} ms")
            lines.append(f"  Max:    {s['maximum'] / 1_000_000.0:.3f} ms")
            lines.append(f"  Mean:   {s['mean'] / 1_000_000.0:.3f} ms")
            lines.append(f"  Median: {s['median'] / 1_000_000.0:.3f} ms")
            lines.append(f"  p95:    {s['p95'] / 1_000_000.0:.3f} ms")
            lines.append("")
        out_str = "\n".join(lines)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(out_str)
        except Exception as e:
            exit_error(args, "S3_BENCH_WRITE_FAILED", f"Failed to write output to {args.output}: {e}")
    else:
        print(out_str, end="" if args.format == "json" else "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
