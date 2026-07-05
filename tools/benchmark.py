#!/usr/bin/env python3
"""In-process benchmark runner for S3."""

import argparse
import datetime
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

try:
    from bootstrap.s3 import OptimizationLevel, compile_source, run_source
    from bootstrap.s3.assembly import ASSEMBLY_FORMAT_VERSION
    from bootstrap.s3.backends.x86_64.backend import generate_native_assembly
    from bootstrap.s3.diagnostics import DIAGNOSTIC_SCHEMA_VERSION
    from bootstrap.s3.ir_serialization import IR_FORMAT_VERSION
except ImportError:
    pass  # We will handle failures during execution, not at import time, but typically this runs inside the repo.

BENCHMARK_FORMAT_VERSION = "1.0.0"

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
        subprocess.check_call(
            ["git", "diff", "--quiet", "HEAD"], stderr=subprocess.DEVNULL
        )
        return "false"
    except subprocess.CalledProcessError:
        return "true"
    except Exception:
        return "unknown"

def sanitize_processor(proc: str) -> str:
    # Just a basic sanitization if needed, though platform.processor() is usually fine
    return proc.strip()

def gather_metadata(args, workloads_order: list[str]) -> dict:
    meta = {
        "benchmark_format_version": BENCHMARK_FORMAT_VERSION,
        "commit": get_git_commit(),
        "dirty": is_git_dirty(),
        "distribution": "0.7.0",
        "source_syntax": "0.6",
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
    return meta

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
    n = len(s)
    rank = math.ceil(0.95 * n)
    idx = rank - 1
    return s[idx]

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
    args = parse_args()
    
    root_dir = Path(__file__).resolve().parent.parent
    manifest_path = root_dir / "benchmarks" / "manifest.json"
    
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)
        
    manifest = load_manifest(manifest_path)
    workloads = manifest.get("workloads", [])
    
    if args.list:
        for w in workloads:
            print(w["id"])
        sys.exit(0)
        
    if args.warmups < 0:
        print("Warmups must be >= 0", file=sys.stderr)
        sys.exit(1)
        
    if args.runs <= 0:
        print("Runs must be > 0", file=sys.stderr)
        sys.exit(1)
        
    if not args.mode or not args.optimization or not args.workload:
        print("Missing required arguments for benchmarking.", file=sys.stderr)
        sys.exit(1)
        
    opt_level = OptimizationLevel.O1 if args.optimization == "O1" else OptimizationLevel.O0
    
    if args.workload == "all":
        selected_workloads = workloads
    else:
        selected_workloads = [w for w in workloads if w["id"] == args.workload]
        if not selected_workloads:
            print(f"Unknown workload: {args.workload}", file=sys.stderr)
            sys.exit(1)
            
    workloads_order = [w["id"] for w in selected_workloads]
    metadata = gather_metadata(args, workloads_order)
    
    results = []
    
    for w in selected_workloads:
        w_path = root_dir / "benchmarks" / w["file"]
        with w_path.open("r", encoding="utf-8") as f:
            source = f.read()
            
        expected_ret = w["expected_return"]
        max_inst = w["max_instructions"]
        max_frames = w.get("max_frames")
        
        # Validation run
        try:
            if args.mode == "hosted-pipeline":
                ret = run_hosted_pipeline(source, opt_level, max_inst, max_frames)
                if ret != expected_ret:
                    print(f"Workload {w['id']} failed: expected {expected_ret}, got {ret}", file=sys.stderr)
                    sys.exit(1)
            else:
                out = run_native_asm_pipeline(source, opt_level, max_inst, max_frames)
                if not out or not isinstance(out, str):
                    print(f"Workload {w['id']} failed: no output for native-asm", file=sys.stderr)
                    sys.exit(1)
        except Exception as e:
            print(f"Workload {w['id']} failed with exception: {e}", file=sys.stderr)
            sys.exit(1)
            
        # Warmups
        for _ in range(args.warmups):
            if args.mode == "hosted-pipeline":
                ret = run_hosted_pipeline(source, opt_level, max_inst, max_frames)
                if ret != expected_ret:
                    print(f"Warmup failed for {w['id']}", file=sys.stderr)
                    sys.exit(1)
            else:
                out = run_native_asm_pipeline(source, opt_level, max_inst, max_frames)
                if not out:
                    print(f"Warmup failed for {w['id']}", file=sys.stderr)
                    sys.exit(1)
                    
        # Runs
        samples = []
        for _ in range(args.runs):
            start_ns = time.perf_counter_ns()
            if args.mode == "hosted-pipeline":
                ret = run_hosted_pipeline(source, opt_level, max_inst, max_frames)
                end_ns = time.perf_counter_ns()
                if ret != expected_ret:
                    print(f"Run failed for {w['id']}", file=sys.stderr)
                    sys.exit(1)
            else:
                out = run_native_asm_pipeline(source, opt_level, max_inst, max_frames)
                end_ns = time.perf_counter_ns()
                if not out:
                    print(f"Run failed for {w['id']}", file=sys.stderr)
                    sys.exit(1)
            samples.append(end_ns - start_ns)
            
        res = {
            "workload": w["id"],
            "status": "passed",
            "expected_return": expected_ret,
            "actual_return": expected_ret,
            "statistics": {
                "unit": "ns",
                "minimum": calc_min(samples),
                "maximum": calc_max(samples),
                "mean": calc_mean(samples),
                "median": calc_median(samples),
                "p95": calc_p95(samples),
            }
        }
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
        out_str = json.dumps(output_data, indent=2, ensure_ascii=False)
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
            print(f"Failed to write output to {args.output}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(out_str)

if __name__ == "__main__":
    main()
