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

# Direct imports
from bootstrap.s3 import OptimizationLevel, compile_source, run_source
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.assembly import ASSEMBLY_FORMAT_VERSION
from bootstrap.s3.backends.x86_64.backend import generate_native_assembly
from bootstrap.s3.diagnostics import DIAGNOSTIC_SCHEMA_VERSION
from bootstrap.s3.ir_serialization import IR_FORMAT_VERSION

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

BENCHMARK_FORMAT_VERSION = "1.0.0"

def extract_format_and_output():
    fmt = "text"
    output = None
    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        if idx + 1 < len(sys.argv):
            fmt = sys.argv[idx + 1]
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output = sys.argv[idx + 1]

    class MockArgs:
        pass
    a = MockArgs()
    a.format = fmt
    a.output = output
    return a

def exit_error(args, code: str, message: str):
    fmt = getattr(args, "format", "text")
    out = getattr(args, "output", None)

    if fmt == "json":
        err_obj = {
            "benchmark_format_version": BENCHMARK_FORMAT_VERSION,
            "status": "error",
            "error": {
                "code": code,
                "message": message
            }
        }
        out_str = json.dumps(err_obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if out:
            try:
                with open(out, "w", encoding="utf-8") as f:
                    f.write(out_str)
            except OSError as e:
                err_obj2 = {
                    "benchmark_format_version": BENCHMARK_FORMAT_VERSION,
                    "status": "error",
                    "error": {
                        "code": "S3_BENCH_WRITE_FAILED",
                        "message": f"Failed to write output to {out}: {e}"
                    }
                }
                print(json.dumps(err_obj2, indent=2, ensure_ascii=False, allow_nan=False), file=sys.stderr)
                sys.exit(1)
            sys.exit(1)
        else:
            print(out_str, end="")
            sys.exit(1)
    else:
        print(f"Error ({code}): {message}", file=sys.stderr)
        sys.exit(1)

class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        args = extract_format_and_output()
        exit_error(args, "S3_BENCH_INVALID_ARGUMENT", message)

def get_distribution_version() -> str:
    try:
        return importlib.metadata.version("s3-bootstrap")
    except importlib.metadata.PackageNotFoundError:
        pass

    if tomllib:
        try:
            checkout_root = Path(__file__).resolve().parent.parent
            pyproject_path = checkout_root / "pyproject.toml"
            if pyproject_path.exists():
                with pyproject_path.open("rb") as f:
                    data = tomllib.load(f)
                return data["project"]["version"]
        except Exception:
            pass
    return "unavailable"

def syntax_mode_to_string(mode: SyntaxMode) -> str:
    if mode == SyntaxMode.V0_5:
        return "0.5"
    if mode == SyntaxMode.V0_6:
        return "0.6"
    return str(mode)

def get_git_commit() -> str:
    cwd = Path(__file__).resolve().parent.parent
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, cwd=cwd
        ).decode("utf-8").strip()
        return commit if commit else "unavailable"
    except Exception:
        return "unavailable"

def is_git_dirty() -> str:
    cwd = Path(__file__).resolve().parent.parent
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            stderr=subprocess.DEVNULL, cwd=cwd
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
        "mode": getattr(args, "mode", "unknown"),
        "optimization": getattr(args, "optimization", "unknown"),
        "warmups": getattr(args, "warmups", 0),
        "runs": getattr(args, "runs", 0),
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
    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        raise ValueError("Invalid JSON")

    if data.get("manifest_version") != "1.0.0":
        raise ValueError("Unsupported manifest version")

    workloads = data.get("workloads")
    if not isinstance(workloads, list) or not workloads:
        raise ValueError("Workloads must be a non-empty list")

    valid_ids = {"minimal", "arithmetic", "branches", "calls", "recursion", "arrays", "optimizer_stress"}
    seen_ids = set()

    benchmarks_dir = manifest_path.parent

    for w in workloads:
        w_id = w.get("id")
        if not isinstance(w_id, str):
            raise ValueError("Invalid or missing ID in workload")
        if w_id in seen_ids:
            raise ValueError(f"Duplicate workload ID: {w_id}")
        seen_ids.add(w_id)

        file_path = w.get("file")
        if not isinstance(file_path, str):
            raise ValueError(f"Invalid file for workload {w_id}")

        if Path(file_path).is_absolute():
            raise ValueError(f"Absolute path in workload {w_id}")
        if ".." in file_path:
            raise ValueError(f"Path traversal in workload {w_id}")

        full_path = (benchmarks_dir / file_path).resolve()
        try:
            full_path.relative_to(benchmarks_dir.resolve())
        except ValueError:
            raise ValueError(f"Path traversal in workload {w_id}")

        if not full_path.exists():
            raise ValueError(f"File {file_path} does not exist")

        expected_return = w.get("expected_return")
        if not isinstance(expected_return, int):
            raise ValueError(f"Invalid expected_return in {w_id}")

        max_instructions = w.get("max_instructions")
        if not isinstance(max_instructions, int) or max_instructions <= 0:
            raise ValueError(f"Invalid max_instructions in {w_id}")

        max_frames = w.get("max_frames")
        if not isinstance(max_frames, int) or max_frames <= 0:
            raise ValueError(f"Invalid max_frames in {w_id}")

    if seen_ids != valid_ids:
        raise ValueError("Manifest must contain exactly the seven official workloads")

    return data

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
    parser = JsonArgumentParser(description="In-process benchmark runner for S3")
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

def write_output(args, out_str: str):
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(out_str)
        except OSError as e:
            if args.format == "json":
                err_obj = {
                    "benchmark_format_version": BENCHMARK_FORMAT_VERSION,
                    "status": "error",
                    "error": {
                        "code": "S3_BENCH_WRITE_FAILED",
                        "message": f"Failed to write output to {args.output}: {e}"
                    }
                }
                print(json.dumps(err_obj, indent=2, ensure_ascii=False, allow_nan=False), file=sys.stderr)
            else:
                print(f"Error (S3_BENCH_WRITE_FAILED): Failed to write output to {args.output}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(out_str, end="" if args.format == "json" else "\n")

def main():
    args = parse_args()

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
            out_obj = {
                "benchmark_format_version": BENCHMARK_FORMAT_VERSION,
                "status": "success",
                "workloads": [
                    {"id": w["id"], "description": w.get("description", "")} for w in workloads
                ]
            }
            out_str = json.dumps(out_obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
            write_output(args, out_str)
        else:
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

        functional_validation = None

        if args.mode == "native-asm-pipeline":
            # 1. Functional validation in hosted pipeline
            try:
                actual = run_hosted_pipeline(source, opt_level, max_inst, max_frames)
            except Exception as e:
                exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Workload {w['id']} functional validation failed with exception: {e}")
            if actual != expected_ret:
                exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Workload {w['id']} functional validation failed: expected {expected_ret}, got {actual}")

            functional_validation = {
                "mode": "hosted-pipeline",
                "status": "passed",
                "expected_return": expected_ret,
                "actual_return": actual
            }

            # 2. Determinism check
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

        else:
            # For hosted pipeline, we just want to run once to fail early if invalid
            try:
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
            res["functional_validation"] = functional_validation
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

    write_output(args, out_str)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
