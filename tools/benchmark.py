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
import tempfile
import tomllib
from pathlib import Path

# Direct imports
from bootstrap.s3 import OptimizationLevel
from bootstrap.s3.lexer import SyntaxMode, tokenize
from bootstrap.s3.parser import parse_tokens
from bootstrap.s3.semantic import analyze
from bootstrap.s3.lowering import lower
from bootstrap.s3.optimizer import optimize_ir
from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.emulator import Emulator, DEFAULT_MAX_FRAMES
from bootstrap.s3.assembly import ASSEMBLY_FORMAT_VERSION
from bootstrap.s3.backends.x86_64.backend import generate_native_assembly
from bootstrap.s3.diagnostics import DIAGNOSTIC_SCHEMA_VERSION
from bootstrap.s3.ir_serialization import IR_FORMAT_VERSION
from bootstrap.s3.metrics import PhaseTimer

if __package__:
    from . import benchmark_statistics as _benchmark_statistics
    from .benchmark_native import (
        NativeBuildError,
        NativeBuildRequest,
        NativeExecutionError,
        NativeSamplingError,
        NativeSamplingPlan,
        NativeSamplingResult,
        run_native_sampling_case,
    )
else:
    import benchmark_statistics as _benchmark_statistics
    from benchmark_native import (
        NativeBuildError,
        NativeBuildRequest,
        NativeExecutionError,
        NativeSamplingError,
        NativeSamplingPlan,
        NativeSamplingResult,
        run_native_sampling_case,
    )

calc_max = _benchmark_statistics.calc_max
calc_mean = _benchmark_statistics.calc_mean
calc_median = _benchmark_statistics.calc_median
calc_min = _benchmark_statistics.calc_min
calc_p95 = _benchmark_statistics.calc_p95
calc_stats = _benchmark_statistics.calc_stats

BENCHMARK_FORMAT_VERSION = "1.2.0"
# The deterministic E2 baseline is a historical artifact generated with the
# public benchmark report format that existed at the time. Keep that source
# format explicit so new public reports can evolve without rewriting the
# tracked baseline.
DETERMINISTIC_BASELINE_SOURCE_FORMAT_VERSION = "1.1.0"

ELF_EXECUTION_MODE = "elf-execution"
ELF_ARTIFACT_KIND = "elf-linux-x86-64"

def extract_format_and_output():
    fmt = "text"
    output = None
    for i, arg in enumerate(sys.argv):
        if arg == "--format" and i + 1 < len(sys.argv):
            fmt = sys.argv[i + 1]
        elif arg.startswith("--format="):
            fmt = arg.split("=", 1)[1]
        elif arg == "--output" and i + 1 < len(sys.argv):
            output = sys.argv[i + 1]
        elif arg.startswith("--output="):
            output = arg.split("=", 1)[1]

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

def get_installed_distribution_version() -> str:
    try:
        return importlib.metadata.version("s3-bootstrap")
    except Exception:
        return "unavailable"

def get_checkout_distribution_version() -> str:
    try:
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            pyproject_data = tomllib.load(f)
        return pyproject_data["project"]["version"]
    except Exception:
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
        "checkout_distribution_version": get_checkout_distribution_version(),
        "installed_distribution_version": get_installed_distribution_version(),
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


def is_linux_x86_64() -> bool:
    system = platform.system()
    machine = platform.machine().lower()
    return system == "Linux" and machine in {"x86_64", "amd64"}


def validate_elf_execution_platform(args) -> None:
    if args.mode != ELF_EXECUTION_MODE:
        return
    if is_linux_x86_64():
        return
    detected = f"{platform.system()} {platform.machine()}".strip()
    exit_error(
        args,
        "S3_BENCH_UNSUPPORTED_PLATFORM",
        (
            f"mode {ELF_EXECUTION_MODE} requires Linux x86-64; "
            f"detected {detected or 'unknown platform'}"
        ),
    )


def validate_elf_timeout(args) -> None:
    if args.mode != ELF_EXECUTION_MODE:
        return
    timeout = args.timeout_seconds
    if timeout is None or not math.isfinite(timeout) or timeout <= 0:
        exit_error(
            args,
            "S3_BENCH_INVALID_ARGUMENT",
            "timeout-seconds must be finite and greater than zero",
        )


def ensure_temp_dir_outside_checkout(temp_dir: Path, root_dir: Path) -> None:
    resolved_temp = temp_dir.resolve()
    resolved_root = root_dir.resolve()
    try:
        resolved_temp.relative_to(resolved_root)
    except ValueError:
        return
    raise RuntimeError("benchmark ELF tempdir resolved inside the checkout")


def make_native_build_request(
    workload: dict,
    root_dir: Path,
    output_path: Path,
    optimization: OptimizationLevel,
) -> NativeBuildRequest:
    return NativeBuildRequest(
        workload_id=workload["id"],
        source_path=root_dir / "benchmarks" / workload["file"],
        optimization=optimization,
        expected_return=workload["expected_return"],
        output_path=output_path,
        max_instructions=workload["max_instructions"],
        max_frames=workload["max_frames"],
        source_syntax="0.6",
    )


def serialize_timing_statistics(statistics) -> dict[str, int | float]:
    values = {
        "sample_count": statistics.sample_count,
        "minimum": statistics.minimum,
        "maximum": statistics.maximum,
        "mean": statistics.mean,
        "median": statistics.median,
        "p95": statistics.p95,
    }
    for field, value in values.items():
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"non-finite timing statistic: {field}")
    return values


def serialize_native_sampling_result(
    result: NativeSamplingResult,
) -> dict:
    statistics = serialize_timing_statistics(result.statistics)
    return {
        "workload": result.artifact.workload_id,
        "status": "passed",
        "mode": ELF_EXECUTION_MODE,
        "opt_level": result.artifact.optimization.name,
        "functional_validation": {
            "mode": ELF_EXECUTION_MODE,
            "status": "passed",
            "expected_return": result.artifact.expected_return,
            "actual_return": result.actual_return,
        },
        "timing": {
            "unit": "ns",
            "samples_ns": list(result.samples_ns),
            "elf_execution": statistics,
        },
        "metrics": {
            "native_artifact": {
                "artifact_kind": ELF_ARTIFACT_KIND,
                "size_bytes": result.artifact.size_bytes,
                "sha256": result.artifact.sha256,
            },
            "execution": {
                "build_count": 1,
                "preflight_count": 1,
                "warmups": result.warmups,
                "runs": result.runs,
                "total_execution_count": result.total_execution_count,
            },
        },
    }


def _native_validation_error_message(
    workload_id: str,
    optimization: OptimizationLevel,
    error: NativeSamplingError,
) -> str:
    phase = error.phase.value
    index = "" if error.index is None else f" {error.index}"
    codes = ", ".join(code.value for code in error.failure_codes) or "unknown"
    return (
        f"Native validation failed for workload {workload_id} "
        f"{optimization.name}: phase {phase}{index}; codes: {codes}"
    )


def run_elf_execution_workload(
    workload: dict,
    root_dir: Path,
    optimization: OptimizationLevel,
    args,
) -> dict:
    try:
        plan = NativeSamplingPlan(
            warmups=args.warmups,
            runs=args.runs,
            timeout=args.timeout_seconds,
        )
    except (TypeError, ValueError) as error:
        exit_error(args, "S3_BENCH_INVALID_ARGUMENT", str(error))

    try:
        with tempfile.TemporaryDirectory(prefix="s3-benchmark-elf-") as temp_dir:
            temp_path = Path(temp_dir)
            ensure_temp_dir_outside_checkout(temp_path, root_dir)
            output_path = temp_path / f"{workload['id']}-{optimization.value}"
            request = make_native_build_request(
                workload,
                root_dir,
                output_path,
                optimization,
            )
            sampling_result = run_native_sampling_case(request, plan)
            return serialize_native_sampling_result(sampling_result)
    except NativeBuildError:
        exit_error(
            args,
            "S3_BENCH_NATIVE_BUILD_FAILED",
            (
                f"Native build failed for workload {workload['id']} "
                f"{optimization.name}"
            ),
        )
    except NativeExecutionError:
        exit_error(
            args,
            "S3_BENCH_NATIVE_EXECUTION_FAILED",
            (
                f"Native ELF execution failed for workload {workload['id']} "
                f"{optimization.name}"
            ),
        )
    except NativeSamplingError as error:
        exit_error(
            args,
            "S3_BENCH_NATIVE_VALIDATION_FAILED",
            _native_validation_error_message(
                workload["id"],
                optimization,
                error,
            ),
        )
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        exit_error(
            args,
            "S3_BENCH_NATIVE_SAMPLING_FAILED",
            (
                f"Native sampling failed for workload {workload['id']} "
                f"{optimization.name}: {type(error).__name__}"
            ),
        )


def append_elf_text_result(lines: list[str], result: dict) -> None:
    timing = result["timing"]
    statistics = timing["elf_execution"]
    validation = result["functional_validation"]
    artifact = result["metrics"]["native_artifact"]
    execution = result["metrics"]["execution"]

    lines.append(f"workload: {result['workload']}")
    lines.append(f"mode: {result['mode']}")
    lines.append(f"optimization: {result['opt_level']}")
    lines.append(f"status: {result['status']}")
    lines.append(f"expected return: {validation['expected_return']}")
    lines.append(f"actual return: {validation['actual_return']}")
    lines.append(f"artifact size: {artifact['size_bytes']} bytes")
    lines.append(f"artifact sha256: {artifact['sha256']}")
    lines.append(f"warmups: {execution['warmups']}")
    lines.append(f"runs: {execution['runs']}")
    lines.append(f"total executions: {execution['total_execution_count']}")
    lines.append("")
    lines.append("timing (ns):")
    lines.append(f"  sample count        : {statistics['sample_count']}")
    lines.append(f"  minimum             : {statistics['minimum']}")
    lines.append(f"  maximum             : {statistics['maximum']}")
    lines.append(f"  mean                : {statistics['mean']}")
    lines.append(f"  median              : {statistics['median']}")
    lines.append(f"  p95                 : {statistics['p95']}")
    lines.append("")


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

        description = w.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"Missing or empty description in workload {w_id}")

        file_path = w.get("file")
        if not isinstance(file_path, str):
            raise ValueError(f"Invalid file for workload {w_id}")

        # Phase 4 path validation
        from pathlib import PurePosixPath, PureWindowsPath
        if PurePosixPath(file_path).is_absolute():
            raise ValueError(f"Absolute POSIX path in workload {w_id}")
        if PureWindowsPath(file_path).is_absolute() or file_path.startswith("\\\\"):
            raise ValueError(f"Absolute Windows/UNC path in workload {w_id}")

        for part in PurePosixPath(file_path.replace("\\\\", "/")).parts:
            if part == "..":
                raise ValueError(f"Path traversal in workload {w_id}")

        full_path = (benchmarks_dir / file_path).resolve()
        try:
            full_path.relative_to(benchmarks_dir.resolve())
        except ValueError:
            raise ValueError(f"Path traversal out of benchmarks in workload {w_id}")

        expected_return = w.get("expected_return")
        if not isinstance(expected_return, int) or isinstance(expected_return, bool):
            raise ValueError(f"Invalid expected_return in workload {w_id}")

        max_instructions = w.get("max_instructions")
        if not isinstance(max_instructions, int) or isinstance(max_instructions, bool) or max_instructions < 1:
            raise ValueError(f"Invalid max_instructions in workload {w_id}")

        max_frames = w.get("max_frames")
        if not isinstance(max_frames, int) or isinstance(max_frames, bool) or max_frames < 1:
            raise ValueError(f"Invalid max_frames in workload {w_id}")

    if seen_ids != valid_ids:
        raise ValueError("Manifest must contain exactly the seven official workloads")

    return data

def extract_static_metrics(source: str, ir_program, assembly_program):
    metrics = {
        "source": {
            "source_size_bytes": len(source.encode("utf-8")),
            "source_line_count": len(source.splitlines())
        }
    }
    if ir_program:
        ir_instructions = sum(len(b.instructions) for f in ir_program.functions for b in f.blocks)
        metrics["ir"] = {
            "function_count": len(ir_program.functions),
            "block_count": sum(len(f.blocks) for f in ir_program.functions),
            "instruction_count": ir_instructions,
        }
    if assembly_program:
        asm_opcodes = sum(len(b.instructions) for f in assembly_program.functions for b in f.blocks)
        rendered = assembly_program.render()
        rendered_bytes = rendered.encode("utf-8")
        metrics["s3_assembly"] = {
            "function_count": len(assembly_program.functions),
            "block_count": sum(len(f.blocks) for f in assembly_program.functions),
            "opcode_count": asm_opcodes,
            "textual_size_bytes": len(rendered_bytes),
            "sha256": hashlib.sha256(rendered_bytes).hexdigest(),
        }
    return metrics

def run_hosted_pipeline(source: str, opt: OptimizationLevel, max_inst: int, max_frames: int | None, clock=None):
    clock = clock if clock is not None else time.perf_counter_ns
    timer = PhaseTimer(clock=clock)
    total_start = clock()

    with timer.measure("parsing"):
        tokens = tokenize(source, mode=SyntaxMode.V0_6)
        syntax_tree = parse_tokens(tokens, mode=SyntaxMode.V0_6)

    with timer.measure("semantic_analysis"):
        semantic_model = analyze(syntax_tree)

    with timer.measure("ir_generation"):
        ir_program_unopt = lower(syntax_tree, semantic_model)

    with timer.measure("optimization"):
        ir_program = optimize_ir(ir_program_unopt, opt)

    with timer.measure("assembly_generation"):
        assembly_program = generate_assembly(ir_program)

    with timer.measure("emulation"):
        emulator = Emulator(
            max_frames=max_frames if max_frames is not None else DEFAULT_MAX_FRAMES,
            max_instructions=max_inst,
            enable_metrics=True,
        )
        actual = emulator.execute(assembly_program, "main")

    total_end = clock()
    total_ns = total_end - total_start
    phases = timer.snapshot()
    measured_total_ns = sum(phases.values())
    overhead_ns = total_ns - measured_total_ns
    if overhead_ns < 0:
        raise ValueError(f"Inconsistent timing: overhead is negative {overhead_ns}")

    static_metrics = extract_static_metrics(source, ir_program, assembly_program)
    dynamic_metrics = {
        "execution": {
            "executed_s3_opcodes": emulator.metrics.executed_s3_opcodes if emulator.metrics else 0,
            "maximum_frame_depth_observed": emulator.metrics.maximum_frame_depth_observed if emulator.metrics else 0,
            "function_call_count": emulator.metrics.function_call_count if emulator.metrics else 0,
        }
    }

    return actual, phases, static_metrics, dynamic_metrics, total_ns, measured_total_ns, overhead_ns

def run_native_asm_pipeline(source: str, opt: OptimizationLevel, max_inst: int, max_frames: int | None, clock=None):
    clock = clock if clock is not None else time.perf_counter_ns
    timer = PhaseTimer(clock=clock)
    total_start = clock()

    with timer.measure("parsing"):
        tokens = tokenize(source, mode=SyntaxMode.V0_6)
        syntax_tree = parse_tokens(tokens, mode=SyntaxMode.V0_6)

    with timer.measure("semantic_analysis"):
        semantic_model = analyze(syntax_tree)

    with timer.measure("ir_generation"):
        ir_program_unopt = lower(syntax_tree, semantic_model)

    with timer.measure("optimization"):
        ir_program = optimize_ir(ir_program_unopt, opt)

    with timer.measure("assembly_generation"):
        assembly_program = generate_assembly(ir_program)

    with timer.measure("native_x86_64_emission"):
        out = generate_native_assembly(
            assembly_program,
            max_frames=max_frames if max_frames is not None else DEFAULT_MAX_FRAMES,
            max_instructions=max_inst,
        )

    total_end = clock()
    total_ns = total_end - total_start
    phases = timer.snapshot()
    measured_total_ns = sum(phases.values())
    overhead_ns = total_ns - measured_total_ns
    if overhead_ns < 0:
        raise ValueError("Inconsistent timing: overhead is negative")

    static_metrics = extract_static_metrics(source, ir_program, assembly_program)

    static_metrics["native_artifact"] = {
        "artifact_kind": "gnu-x86-64-assembly",
        "textual_size_bytes": len(out.encode("utf-8")),
        "line_count": len(out.splitlines()),
        "sha256": hashlib.sha256(out.encode("utf-8")).hexdigest()
    }

    return out, phases, static_metrics, total_ns, measured_total_ns, overhead_ns

def run_workload(w, source, opt_level, max_inst, max_frames, args, clock=None):
    expected_ret = w["expected_return"]
    functional_validation = None

    if args.mode == "native-asm-pipeline":
        # 1. Functional validation in hosted pipeline
        try:
            actual, _, _, dyn_metrics, _, _, _ = run_hosted_pipeline(source, opt_level, max_inst, max_frames, clock=clock)
        except Exception as e:
            exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Workload {w['id']} functional validation failed with exception: {e}")
        if actual != expected_ret:
            exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Workload {w['id']} functional validation failed: expected {expected_ret}, got {actual}")

        functional_validation = {
            "mode": "hosted-pipeline",
            "status": "passed",
            "expected_return": expected_ret,
            "actual_return": actual,
            "metrics": dyn_metrics
        }

        # 2. Determinism check
        try:
            out1, _, static_metrics1, _, _, _ = run_native_asm_pipeline(source, opt_level, max_inst, max_frames, clock=clock)
            out2, _, _, _, _, _ = run_native_asm_pipeline(source, opt_level, max_inst, max_frames, clock=clock)
        except TypeError as e:
            exit_error(args, "S3_BENCH_NATIVE_TYPE_ERROR", str(e))
        except Exception as e:
            exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Workload {w['id']} failed during determinism check: {e}")

        if not out1 or not out2:
            exit_error(args, "S3_BENCH_NATIVE_EMPTY", f"Workload {w['id']} generated empty output")
        if out1 != out2:
            exit_error(args, "S3_BENCH_NATIVE_NON_DETERMINISTIC", f"Workload {w['id']} native asm output is non-deterministic")

        static_metrics_for_json = static_metrics1
    else:
        # For hosted pipeline, we just want to run once to fail early if invalid
        try:
            actual, _, static_metrics_for_json, dynamic_metrics_for_json, _, _, _ = run_hosted_pipeline(source, opt_level, max_inst, max_frames, clock=clock)
            if actual != expected_ret:
                exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Workload {w['id']} failed: expected {expected_ret}, got {actual}")
        except Exception as e:
            exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Workload {w['id']} failed with exception: {e}")

    # Warmups
    for _ in range(args.warmups):
        if args.mode == "hosted-pipeline":
            actual, _, _, _, _, _, _ = run_hosted_pipeline(source, opt_level, max_inst, max_frames, clock=clock)
            if actual != expected_ret:
                exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Warmup failed for {w['id']}")
        else:
            try:
                out, _, _, _, _, _ = run_native_asm_pipeline(source, opt_level, max_inst, max_frames, clock=clock)
            except TypeError as e:
                exit_error(args, "S3_BENCH_NATIVE_TYPE_ERROR", str(e))
            if not out:
                exit_error(args, "S3_BENCH_NATIVE_EMPTY", f"Warmup failed for {w['id']}: empty output")

    # Runs
    total_samples = []
    measured_samples = []
    overhead_samples = []
    phase_samples = {}

    actual_for_json = None
    for _ in range(args.runs):
        if args.mode == "hosted-pipeline":
            actual, run_phases, _, _, total_ns, measured_ns, overhead_ns = run_hosted_pipeline(source, opt_level, max_inst, max_frames, clock=clock)
            if actual != expected_ret:
                exit_error(args, "S3_BENCH_INCORRECT_RESULT", f"Run failed for {w['id']}")
            actual_for_json = actual
        else:
            try:
                out, run_phases, _, total_ns, measured_ns, overhead_ns = run_native_asm_pipeline(source, opt_level, max_inst, max_frames, clock=clock)
            except TypeError as e:
                exit_error(args, "S3_BENCH_NATIVE_TYPE_ERROR", str(e))
            if not out:
                exit_error(args, "S3_BENCH_NATIVE_EMPTY", f"Run failed for {w['id']}: empty output")

        total_samples.append(total_ns)
        measured_samples.append(measured_ns)
        overhead_samples.append(overhead_ns)

        for k, v in run_phases.items():
            if k not in phase_samples:
                phase_samples[k] = []
            phase_samples[k].append(v)

    phases_out = {}
    for p_name, p_samples in phase_samples.items():
        phases_out[p_name] = calc_stats(p_samples)

    res = {
        "workload": w["id"],
        "status": "passed",
        "opt_level": opt_level.name,
        "timing": {
            "unit": "ns",
            "pipeline_total": calc_stats(total_samples),
            "measured_phases_total": calc_stats(measured_samples),
            "unclassified_overhead": calc_stats(overhead_samples),
            "phases": phases_out
        },
        "metrics": static_metrics_for_json
    }

    if args.mode == "hosted-pipeline":
        res["expected_return"] = expected_ret
        res["actual_return"] = actual_for_json
        res["metrics"].update(dynamic_metrics_for_json)
    else:
        res["functional_validation"] = functional_validation

    if args.include_samples:
        res["timing"]["samples_ns"] = {
            "pipeline_total": total_samples,
            "measured_phases_total": measured_samples,
            "unclassified_overhead": overhead_samples,
            "phases": phase_samples
        }

    return res

def parse_args():
    parser = JsonArgumentParser(description="In-process benchmark runner for S3")
    parser.add_argument("--list", action="store_true", help="List available workloads")
    parser.add_argument(
        "--mode",
        choices=["hosted-pipeline", "native-asm-pipeline", ELF_EXECUTION_MODE],
        help="Benchmark mode",
    )
    parser.add_argument("--optimization", choices=["O0", "O1", "both"], help="Optimization level")
    parser.add_argument("--workload", help="Workload ID or 'all'")
    parser.add_argument("--warmups", type=int, default=3, help="Number of warmups")
    parser.add_argument("--runs", type=int, default=10, help="Number of measured runs")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help=(
            "Defensive timeout for each ELF execution in elf-execution mode"
        ),
    )
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

    validate_elf_timeout(args)

    if args.workload == "all":
        selected_workloads = workloads
    else:
        selected_workloads = [w for w in workloads if w["id"] == args.workload]
        if not selected_workloads:
            exit_error(args, "S3_BENCH_UNKNOWN_WORKLOAD", f"Unknown workload: {args.workload}")

    validate_elf_execution_platform(args)

    workloads_order = [w["id"] for w in selected_workloads]
    metadata = gather_metadata(args, workloads_order)

    results = []

    for w in selected_workloads:
        max_inst = w["max_instructions"]
        max_frames = w.get("max_frames")

        if args.optimization == "both":
            if args.mode == ELF_EXECUTION_MODE:
                res_O0 = run_elf_execution_workload(
                    w,
                    root_dir,
                    OptimizationLevel.O0,
                    args,
                )
                res_O1 = run_elf_execution_workload(
                    w,
                    root_dir,
                    OptimizationLevel.O1,
                    args,
                )
                results.append({
                    "workload": w["id"],
                    "status": "passed",
                    "O0": res_O0,
                    "O1": res_O1,
                })
                continue

            w_path = root_dir / "benchmarks" / w["file"]
            try:
                with w_path.open("r", encoding="utf-8") as f:
                    source = f.read()
            except Exception as e:
                exit_error(args, "S3_BENCH_INVALID_MANIFEST", f"Failed to read workload source: {e}")

            res_O0 = run_workload(w, source, OptimizationLevel.O0, max_inst, max_frames, args)
            res_O1 = run_workload(w, source, OptimizationLevel.O1, max_inst, max_frames, args)

            # comparison
            def _diff_and_pct(v0, v1):
                diff = v1 - v0
                pct = (diff / v0 * 100.0) if v0 != 0 else None
                lbl = "equal"
                if diff < 0:
                    lbl = "fewer"
                elif diff > 0:
                    lbl = "more"
                return diff, pct, lbl

            def _time_diff(v0, v1):
                diff = v1 - v0
                pct = (diff / v0 * 100.0) if v0 != 0 else None
                lbl = "equal_in_this_run"
                if diff < 0:
                    lbl = "faster_in_this_run"
                elif diff > 0:
                    lbl = "slower_in_this_run"
                return diff, pct, lbl

            comp = {
                "O0_return": res_O0.get("actual_return", res_O0.get("functional_validation", {}).get("actual_return")),
                "O1_return": res_O1.get("actual_return", res_O1.get("functional_validation", {}).get("actual_return")),
            }
            comp["equal_return"] = comp["O0_return"] == comp["O1_return"]

            # S3 Opcode count
            o0_s3_opcode = res_O0["metrics"].get("s3_assembly", {}).get("opcode_count", 0)
            o1_s3_opcode = res_O1["metrics"].get("s3_assembly", {}).get("opcode_count", 0)
            diff, pct, lbl = _diff_and_pct(o0_s3_opcode, o1_s3_opcode)
            comp["O0_s3_opcode_count"] = o0_s3_opcode
            comp["O1_s3_opcode_count"] = o1_s3_opcode
            comp["s3_opcode_count_diff"] = diff
            comp["s3_opcode_count_percent"] = pct
            comp["s3_opcode_count_label"] = lbl

            # Executed S3 opcodes
            if "execution" in res_O0["metrics"]:
                o0_exec = res_O0["metrics"]["execution"].get("executed_s3_opcodes", 0)
                o1_exec = res_O1["metrics"]["execution"].get("executed_s3_opcodes", 0)
                diff, pct, lbl = _diff_and_pct(o0_exec, o1_exec)
                comp["O0_executed_s3_opcodes"] = o0_exec
                comp["O1_executed_s3_opcodes"] = o1_exec
                comp["executed_s3_opcodes_diff"] = diff
                comp["executed_s3_opcodes_percent"] = pct
                comp["executed_s3_opcodes_label"] = lbl

            # S3 textual size
            o0_text = res_O0["metrics"].get("s3_assembly", {}).get("textual_size_bytes", 0)
            o1_text = res_O1["metrics"].get("s3_assembly", {}).get("textual_size_bytes", 0)
            diff, pct, lbl = _diff_and_pct(o0_text, o1_text)
            comp["O0_s3_textual_size_bytes"] = o0_text
            comp["O1_s3_textual_size_bytes"] = o1_text
            comp["s3_textual_size_diff"] = diff

            # GNU textual size
            if "native_artifact" in res_O0["metrics"]:
                o0_gnu = res_O0["metrics"]["native_artifact"].get("textual_size_bytes", 0)
                o1_gnu = res_O1["metrics"]["native_artifact"].get("textual_size_bytes", 0)
                diff, pct, lbl = _diff_and_pct(o0_gnu, o1_gnu)
                comp["O0_gnu_textual_size_bytes"] = o0_gnu
                comp["O1_gnu_textual_size_bytes"] = o1_gnu
                comp["gnu_textual_size_diff"] = diff

            # Hashes
            comp["O0_s3_assembly_sha256"] = res_O0["metrics"].get("s3_assembly", {}).get("sha256")
            comp["O1_s3_assembly_sha256"] = res_O1["metrics"].get("s3_assembly", {}).get("sha256")
            if "native_artifact" in res_O0["metrics"]:
                comp["O0_gnu_assembly_sha256"] = res_O0["metrics"]["native_artifact"].get("sha256")
                comp["O1_gnu_assembly_sha256"] = res_O1["metrics"]["native_artifact"].get("sha256")

            # Timing info
            o0_time = res_O0["timing"]["pipeline_total"]["median"]
            o1_time = res_O1["timing"]["pipeline_total"]["median"]
            diff, pct, lbl = _time_diff(o0_time, o1_time)
            comp["O0_pipeline_median_ns"] = o0_time
            comp["O1_pipeline_median_ns"] = o1_time
            comp["pipeline_median_diff_ns"] = diff
            comp["pipeline_median_percent"] = pct
            comp["pipeline_median_label"] = lbl

            results.append({
                "workload": w["id"],
                "status": "passed",
                "O0": res_O0,
                "O1": res_O1,
                "comparison": comp
            })
        else:
            opt_lvl = OptimizationLevel.O1 if args.optimization == "O1" else OptimizationLevel.O0
            if args.mode == ELF_EXECUTION_MODE:
                results.append(
                    run_elf_execution_workload(w, root_dir, opt_lvl, args)
                )
            else:
                w_path = root_dir / "benchmarks" / w["file"]
                try:
                    with w_path.open("r", encoding="utf-8") as f:
                        source = f.read()
                except Exception as e:
                    exit_error(args, "S3_BENCH_INVALID_MANIFEST", f"Failed to read workload source: {e}")
                results.append(run_workload(w, source, opt_lvl, max_inst, max_frames, args))

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
        for top_r in results:
            if "comparison" in top_r or ("O0" in top_r and "O1" in top_r):
                rs = [top_r["O0"], top_r["O1"]]
            else:
                rs = [top_r]

            for r in rs:
                if r.get("mode") == ELF_EXECUTION_MODE:
                    append_elf_text_result(lines, r)
                    continue

                lines.append(f"workload: {r['workload']}")
                lines.append(f"mode: {args.mode}")
                lines.append(f"optimization: {r['opt_level']}")
                t = r["timing"]
                lines.append(f"median total: {t['pipeline_total']['median'] / 1_000_000.0:.3f} ms")
                lines.append("")
                lines.append("phases:")
                for p_name, p_data in t["phases"].items():
                    lines.append(f"  {p_name:<20}: {p_data['median'] / 1_000_000.0:.3f} ms")
                lines.append(f"  {'measured sum':<20}: {t['measured_phases_total']['median'] / 1_000_000.0:.3f} ms")
                lines.append(f"  {'unclassified':<20}: {t['unclassified_overhead']['median'] / 1_000_000.0:.3f} ms")
                lines.append("")

                lines.append("metrics:")
                m = r["metrics"]
                if "s3_assembly" in m:
                    lines.append(f"  S3 opcodes emitted:   {m['s3_assembly'].get('opcode_count', 0)}")
                    lines.append(f"  functions:            {m['s3_assembly'].get('function_count', 0)}")
                    lines.append(f"  blocks:               {m['s3_assembly'].get('block_count', 0)}")
                if "execution" in m:
                    lines.append(f"  S3 opcodes executed:  {m['execution'].get('executed_s3_opcodes', 0)}")
                    lines.append(f"  max frame depth:      {m['execution'].get('maximum_frame_depth_observed', 0)}")
                    lines.append(f"  function calls:       {m['execution'].get('function_call_count', 0)}")
                if "native_artifact" in m:
                    lines.append(f"  native size:          {m['native_artifact'].get('textual_size_bytes', 0)} bytes")
                    lines.append(f"  native sha256:        {m['native_artifact'].get('sha256', '')[:8]}...")

                lines.append("")

            if "comparison" in top_r:
                lines.append("comparison (O0 vs O1):")
                c = top_r["comparison"]
                for k, v in c.items():
                    lines.append(f"  {k:<30}: {v}")
                lines.append("")

        out_str = "\n".join(lines)

    write_output(args, out_str)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
