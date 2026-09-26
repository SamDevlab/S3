"""Paired Linux x86-64 measurements for the S3 1.5 real-world kernels."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import platform
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MAX_INSTRUCTIONS = 1_000_000_000
DEFAULT_ITERATIONS = 1_000
DEFAULT_WARMUPS = 3
DEFAULT_SAMPLES = 21
SEED = 1501
BOOTSTRAP_RESAMPLES = 10_000
MATERIAL_CHANGE = 0.05

from bootstrap.s3.backends.x86_64 import (  # noqa: E402
    InstructionBudgetMode,
    NativeToolchain,
    X8664Backend,
    generate_ffi_assembly,
)
from bootstrap.s3.optimizer import OptimizationLevel  # noqa: E402
from bootstrap.s3.pipeline import compile_source  # noqa: E402

TOLERANCES = {
    "engineering.point-cloud-summary.v1": (1e-9, 1e-9),
    "geospatial.raster-window-statistics.v1": (1e-9, 1e-9),
    "energy.pv-timeseries-aggregation.v1": (1e-6, 1e-9),
}
OUTPUT_KEYS = {
    "engineering.point-cloud-summary.v1": (
        "centroid_x", "centroid_y", "centroid_z", "minimum_x", "minimum_y", "minimum_z",
        "maximum_x", "maximum_y", "maximum_z", "radius_of_gyration",
    ),
    "geospatial.raster-window-statistics.v1": (
        "valid_sum", "valid_mean", "valid_minimum", "valid_maximum", "threshold_count",
        "horizontal_abs_gradient_mean",
    ),
    "energy.pv-timeseries-aggregation.v1": (
        "ac_energy_wh", "ac_peak_w", "net_energy_wh", "capacity_factor", "mean_absolute_balance_w",
    ),
}


def _run(argv: list[str]) -> str:
    return subprocess.run(argv, check=True, capture_output=True, text=True).stdout


def _perf_capability() -> dict[str, object]:
    perf = shutil.which("perf")
    paranoid_path = Path("/proc/sys/kernel/perf_event_paranoid")
    paranoid = paranoid_path.read_text().strip() if paranoid_path.is_file() else None
    if perf is None:
        return {"status": "UNAVAILABLE_TOOL_MISSING", "perf_event_paranoid": paranoid}
    probe = subprocess.run(
        [perf, "stat", "-e", "cycles", "--", "true"],
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0:
        return {"status": "AVAILABLE_PERMISSION_PROBE_ONLY", "perf_event_paranoid": paranoid}
    detail = (probe.stderr or probe.stdout).strip().splitlines()
    return {
        "status": "UNAVAILABLE_BY_POLICY" if paranoid is not None and int(paranoid) >= 3 else "UNAVAILABLE",
        "perf_event_paranoid": paranoid,
        "probe_exit": probe.returncode,
        "probe_detail": detail[-2:],
    }


def _source_provenance(
    revision: str | None,
    tree: str | None,
    worktree_state: str | None,
) -> dict[str, object]:
    explicit_values = (revision, tree, worktree_state)
    if any(value is not None for value in explicit_values):
        if not all(value is not None for value in explicit_values):
            raise ValueError("explicit source provenance requires commit, tree, and worktree state")
        if worktree_state not in {"clean", "dirty"}:
            raise ValueError("explicit worktree state must be clean or dirty")
        return {
            "git_commit": revision,
            "git_tree": tree,
            "worktree_clean": worktree_state == "clean",
            "identity_source": "explicit_source_checkout_provenance",
        }
    try:
        revision = _run(["git", "rev-parse", "HEAD"]).strip()
        tree = _run(["git", "rev-parse", "HEAD^{tree}"]).strip()
        worktree_clean = not bool(_run(["git", "status", "--porcelain"]).strip())
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("run inside a Git checkout or supply explicit source provenance") from exc
    return {
        "git_commit": revision,
        "git_tree": tree,
        "worktree_clean": worktree_clean,
        "identity_source": "local_git_checkout",
    }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _load_inputs() -> tuple[dict, dict]:
    manifest_path = ROOT / "benchmarks/manifests/s3bench-1.5-real-world.json"
    reference_path = ROOT / "benchmarks/references/s3-1.5/reference-results-v1.json"
    return json.loads(manifest_path.read_text()), json.loads(reference_path.read_text())


def _double_array(values: list[float]):
    return (ctypes.c_double * len(values))(*values)


def _i64_array(values: list[int]):
    return (ctypes.c_int64 * len(values))(*values)


def _make_call(library: ctypes.CDLL, workload: dict, output) -> Callable[[], int]:
    workload_id = workload["workload_id"]
    data = workload["input"]
    if workload_id == "engineering.point-cloud-summary.v1":
        kernel = library.point_cloud_summary
        coordinates = _double_array(data["coordinates"])
        kernel.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int64, ctypes.c_int64,
                           ctypes.POINTER(ctypes.c_double), ctypes.c_int64]
        kernel.restype = ctypes.c_int64
        return lambda: kernel(coordinates, len(coordinates), data["point_count"], output, len(output))
    if workload_id == "geospatial.raster-window-statistics.v1":
        kernel = library.raster_window_statistics
        values = _double_array(data["values"])
        mask = _i64_array(data["valid_mask"])
        kernel.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
                           ctypes.POINTER(ctypes.c_int64), ctypes.c_int64,
                           ctypes.c_int64, ctypes.c_int64, ctypes.c_double,
                           ctypes.POINTER(ctypes.c_double), ctypes.c_int64]
        kernel.restype = ctypes.c_int64
        return lambda: kernel(values, len(values), mask, len(mask), data["width"], data["height"],
                              data["threshold"], output, len(output))
    kernel = library.energy_series_aggregation
    ac = _double_array(data["ac_power_w"])
    load = _double_array(data["load_w"])
    capacity = json.loads((ROOT / "benchmarks/workloads/real_world/datasets-v1.json").read_text())["energy"]["dc_capacity_w"]
    kernel.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
                       ctypes.POINTER(ctypes.c_double), ctypes.c_int64, ctypes.c_double,
                       ctypes.POINTER(ctypes.c_double), ctypes.c_int64]
    kernel.restype = ctypes.c_int64
    return lambda: kernel(ac, len(ac), load, len(load), capacity, output, len(output))


def _compile_s3(
    source: str,
    output: Path,
    level: OptimizationLevel,
    policy: str,
    budget_mode: InstructionBudgetMode = InstructionBudgetMode.PER_INSTRUCTION,
) -> dict[str, object]:
    result = compile_source(source, optimization=level)
    _, program = result.require_ordinary_artifacts()
    backend = X8664Backend(
        max_instructions=MAX_INSTRUCTIONS,
        native_policy=policy,
        instruction_budget_mode=budget_mode,
    )
    policy_summary = backend.explain_native_policy(program).to_dict()
    assembly = generate_ffi_assembly(
        program,
        max_instructions=MAX_INSTRUCTIONS,
        native_policy=policy,
        instruction_budget_mode=budget_mode,
    )
    assembly_path = output.with_suffix(".s")
    toolchain = NativeToolchain.detect()
    toolchain.build_shared(assembly, output, keep_assembly=assembly_path)
    function_name = next(function.name for function in program.functions if function.exported)
    function = next(function for function in program.functions if function.name == function_name)
    return {
        "path": output,
        "assembly_path": assembly_path,
        "source_sha256": _sha256(source.encode()),
        "assembly_sha256": _sha256(assembly.encode()),
        "optimization": level.value,
        "native_policy": policy,
        "instruction_budget_mode": budget_mode.value,
        "native_policy_summary": policy_summary,
        "assembly_opcode_counts": dict(sorted(Counter(item.opcode.value for item in function.instructions).items())),
        "assembly_instruction_count": len(function.instructions),
        "compiler": toolchain.compiler,
        "compiler_version": _run([toolchain.compiler, "--version"]).splitlines()[0],
    }


def _compile_c(output: Path) -> dict[str, object]:
    source_path = ROOT / "benchmarks/workloads/real_world/native_reference_kernels.c"
    compiler = shutil.which("cc")
    if compiler is None:
        raise RuntimeError("cc is required for the native workload comparison")
    flags = ["-O1", "-fno-fast-math", "-ffp-contract=off", "-fno-tree-vectorize", "-fPIC", "-shared"]
    subprocess.run([compiler, *flags, str(source_path), "-lm", "-o", str(output)], check=True)
    return {
        "path": output,
        "source_sha256": _sha256(source_path.read_bytes()),
        "optimization": "-O1",
        "flags": flags,
        "compiler": compiler,
        "compiler_version": _run([compiler, "--version"]).splitlines()[0],
    }


def _binary_metrics(path: Path, symbol: str) -> dict[str, int]:
    section_text_bytes = 0
    for line in _run(["size", "-A", str(path)]).splitlines():
        columns = line.split()
        if columns and columns[0] == ".text":
            section_text_bytes = int(columns[1])
            break
    symbol_bytes = 0
    for line in _run(["nm", "-S", "--defined-only", str(path)]).splitlines():
        columns = line.split()
        if len(columns) >= 4 and columns[-1] == symbol:
            symbol_bytes = int(columns[1], 16)
            break
    disassembly = _run(["objdump", "-d", f"--disassemble={symbol}", str(path)])
    instructions: list[tuple[str, str]] = []
    for line in disassembly.splitlines():
        if ":\t" not in line:
            continue
        fields = line.split("\t")
        if len(fields) >= 3:
            parts = fields[2].strip().split(None, 1)
            if parts:
                instructions.append((parts[0], parts[1] if len(parts) > 1 else ""))
    budget_refs = sum(
        any(
            symbol in operands
            for symbol in (
                "__s3_instruction_count",
                "__s3_instruction_remaining",
            )
        )
        for _, operands in instructions
    )
    stack_frame_bytes = 0
    for mnemonic, operands in instructions:
        if mnemonic == "sub":
            match = re.search(r"\$0x([0-9a-fA-F]+),%rsp", operands)
            if match:
                stack_frame_bytes = int(match.group(1), 16)
    return {
        "elf_file_bytes": path.stat().st_size,
        "text_section_bytes": section_text_bytes,
        "exported_function_bytes": symbol_bytes,
        "static_machine_instructions": len(instructions),
        "static_branches": sum(mnemonic.startswith("j") for mnemonic, _ in instructions),
        "static_calls": sum(mnemonic.startswith("call") for mnemonic, _ in instructions),
        "static_memory_references": sum("(" in operands for _, operands in instructions),
        "static_stack_references": sum("%rsp" in operands or "%rbp" in operands for _, operands in instructions),
        "static_instruction_budget_counter_references": budget_refs,
        "stack_frame_bytes": stack_frame_bytes,
    }


def _check_output(actual: list[float], expected: dict[str, float], workload_id: str) -> None:
    absolute, relative = TOLERANCES[workload_id]
    for value, key in zip(actual, OUTPUT_KEYS[workload_id], strict=True):
        if not math.isclose(value, expected[key], abs_tol=absolute, rel_tol=relative):
            raise AssertionError(f"{workload_id} output mismatch: {key}={value!r}, expected={expected[key]!r}")


def _summary(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    mean = statistics.fmean(ordered)
    return {
        "sample_count": len(ordered),
        "median_ns_per_call": statistics.median(ordered),
        "mean_ns_per_call": mean,
        "p95_ns_per_call": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "minimum_ns_per_call": ordered[0],
        "maximum_ns_per_call": ordered[-1],
        "stddev_ns_per_call": statistics.stdev(ordered),
        "coefficient_of_variation": statistics.stdev(ordered) / mean if mean else 0.0,
    }


def _paired_ratio_summary(baseline: list[float], candidate: list[float], seed: int) -> dict[str, object]:
    if len(baseline) != len(candidate) or len(baseline) < 3:
        raise ValueError("paired comparison requires equal sample counts >= 3")
    ratios = [left / right for left, right in zip(baseline, candidate, strict=True)]
    rng = random.Random(seed)
    bootstrapped = sorted(
        statistics.median(rng.choices(ratios, k=len(ratios)))
        for _ in range(BOOTSTRAP_RESAMPLES)
    )
    low = bootstrapped[int(0.025 * BOOTSTRAP_RESAMPLES)]
    high = bootstrapped[int(0.975 * BOOTSTRAP_RESAMPLES) - 1]
    if low > 1.0 + MATERIAL_CHANGE:
        classification = "MATERIAL_IMPROVEMENT"
    elif high < 1.0 - MATERIAL_CHANGE:
        classification = "MATERIAL_REGRESSION"
    elif low >= 1.0 - MATERIAL_CHANGE and high <= 1.0 + MATERIAL_CHANGE:
        classification = "NO_MATERIAL_CHANGE_WITHIN_5_PERCENT"
    else:
        classification = "INCONCLUSIVE"
    return {
        "baseline_over_candidate_median_ratio": statistics.median(ratios),
        "paired_bootstrap_95_percentile_interval": [low, high],
        "resamples": BOOTSTRAP_RESAMPLES,
        "seed": seed,
        "material_change_threshold": MATERIAL_CHANGE,
        "classification": classification,
    }


def _measure(call: Callable[[], int], iterations: int) -> float:
    start = time.perf_counter_ns()
    for _ in range(iterations):
        call()
    return (time.perf_counter_ns() - start) / iterations


def run(
    output_dir: Path,
    *,
    iterations: int,
    warmups: int,
    samples: int,
    source_revision: str | None = None,
    source_tree: str | None = None,
    source_worktree_state: str | None = None,
) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("native workload characterization requires Linux x86-64")
    if iterations < 1 or warmups < 1 or samples < 3:
        raise ValueError("iterations/warmups must be positive and samples must be >= 3")
    started_at_utc = datetime.now(timezone.utc).isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest, references = _load_inputs()
    manifest_by_id = {item["workload_id"]: item for item in manifest["workloads"]}
    compiler_candidates: dict[str, dict[str, object]] = {}
    c_path = output_dir / "libreal_world_reference.so"
    compiler_candidates["C_O1"] = _compile_c(c_path)
    c_library = ctypes.CDLL(str(c_path))
    results: dict[str, object] = {}
    randomizer = random.Random(SEED)
    workloads = references["workloads"]

    for workload in workloads:
        workload_id = workload["workload_id"]
        spec = manifest_by_id[workload_id]
        if workload["dataset_sha256"] != spec["dataset_sha256"]:
            raise ValueError(f"{workload_id} dataset identity disagrees with manifest")
        if workload["output_sha256"] != spec["expected_output_sha256"]:
            raise ValueError(f"{workload_id} reference output disagrees with manifest")
        source_path = ROOT / "benchmarks" / spec["s3_source"]
        source = source_path.read_text(encoding="utf-8")
        implementations: dict[str, dict[str, object]] = {}
        for level in (OptimizationLevel.O0, OptimizationLevel.O1):
            label = f"S3_{level.value}_BASELINE"
            compiled = _compile_s3(source, output_dir / f"{workload_id}-{level.value.lower()}.so", level, "baseline")
            compiler_candidates[label] = compiled
            implementations[label] = compiled
        compact = _compile_s3(source, output_dir / f"{workload_id}-o1-compact-ea.so", OptimizationLevel.O1, "compact-ea")
        compiler_candidates[f"S3_O1_COMPACT_EA_{workload_id}"] = compact
        implementations[f"S3_O1_COMPACT_EA"] = compact
        for mode in (InstructionBudgetMode.EXACT_SEGMENT, InstructionBudgetMode.LOOP_HYBRID):
            label = f"S3_O1_{mode.name}"
            candidate = _compile_s3(
                source,
                output_dir / f"{workload_id}-o1-{mode.value}.so",
                OptimizationLevel.O1,
                "baseline",
                budget_mode=mode,
            )
            compiler_candidates[f"{label}_{workload_id}"] = candidate
            implementations[label] = candidate
        c_candidate = compiler_candidates["C_O1"]
        implementations["C_O1"] = c_candidate

        output_count = len(OUTPUT_KEYS[workload_id])
        calls: dict[str, Callable[[], int]] = {}
        actual_results: dict[str, list[float]] = {}
        for label, candidate in implementations.items():
            lib = c_library if label == "C_O1" else ctypes.CDLL(str(candidate["path"]))
            output_type = ctypes.c_double * output_count
            output_buffer = output_type()
            call = _make_call(lib, workload, output_buffer)
            status = call()
            if status != 0:
                raise RuntimeError(f"{workload_id} {label} correctness call returned {status}")
            actual = list(output_buffer)
            _check_output(actual, workload["expected_output"], workload_id)
            calls[label] = call
            actual_results[label] = actual

        warmup_checksums: dict[str, str] = {}
        for label, call in calls.items():
            for _ in range(warmups):
                if call() != 0:
                    raise RuntimeError(f"{workload_id} {label} failed in warmup")
            warmup_checksums[label] = _sha256(_json_bytes([round(value, 10) for value in actual_results[label]]))

        labels = list(calls)
        sample_values = {label: [] for label in labels}
        paired_order: list[list[str]] = []
        for sample_index in range(samples):
            start_index = sample_index % len(labels)
            order = labels[start_index:] + labels[:start_index]
            if sample_index % 2:
                order = list(reversed(order))
            paired_order.append(order)
            for label in order:
                sample_values[label].append(_measure(calls[label], iterations))

        policy_by_workload = compact["native_policy_summary"]
        function_summary = policy_by_workload["function_decisions"]
        compact_applied = any(item["applied"] for item in function_summary.values())
        binaries = {}
        for label, candidate in implementations.items():
            exported_symbol = {
                "engineering.point-cloud-summary.v1": "point_cloud_summary",
                "geospatial.raster-window-statistics.v1": "raster_window_statistics",
                "energy.pv-timeseries-aggregation.v1": "energy_series_aggregation",
            }[workload_id]
            binaries[label] = _binary_metrics(Path(candidate["path"]), exported_symbol)

        o1_median = statistics.median(sample_values["S3_O1_BASELINE"])
        c_median = statistics.median(sample_values["C_O1"])
        exact_median = statistics.median(sample_values["S3_O1_EXACT_SEGMENT"])
        hybrid_median = statistics.median(sample_values["S3_O1_LOOP_HYBRID"])
        results[workload_id] = {
            "dataset_id": workload["dataset_id"],
            "dataset_sha256": workload["dataset_sha256"],
            "reference_engine": workload["reference_engine"],
            "reference_engine_version": workload["reference_engine_version"],
            "correctness": "PASS_ALL_BUILDS",
            "native_candidate_output_sha256": warmup_checksums,
            "timing_protocol": {
                "scope": "same-process scalar C ABI calls; input/setup/build excluded; ctypes dispatch included equally",
                "iterations_per_sample": iterations,
                "warmups": warmups,
                "samples": samples,
                "paired_order_seed": SEED,
                "paired_order": paired_order,
                "paired_bootstrap_resamples": BOOTSTRAP_RESAMPLES,
                "material_change_threshold": MATERIAL_CHANGE,
                "timing_clock": "time.perf_counter_ns",
            },
            "timings": {label: _summary(values) for label, values in sample_values.items()},
            "paired_comparisons": {
                "s3_o1_vs_c_o1": _paired_ratio_summary(
                    sample_values["S3_O1_BASELINE"], sample_values["C_O1"], SEED + 1
                ),
                "o0_vs_o1": _paired_ratio_summary(
                    sample_values["S3_O0_BASELINE"], sample_values["S3_O1_BASELINE"], SEED + 2
                ),
                "per_vs_exact_segment": _paired_ratio_summary(
                    sample_values["S3_O1_BASELINE"], sample_values["S3_O1_EXACT_SEGMENT"], SEED + 3
                ),
                "per_vs_loop_hybrid": _paired_ratio_summary(
                    sample_values["S3_O1_BASELINE"], sample_values["S3_O1_LOOP_HYBRID"], SEED + 4
                ),
                "baseline_vs_compact_ea": _paired_ratio_summary(
                    sample_values["S3_O1_BASELINE"], sample_values["S3_O1_COMPACT_EA"], SEED + 5
                ),
            },
            "o1_s3_over_c_ratio": o1_median / c_median,
            "per_over_exact_segment_ratio": o1_median / exact_median,
            "per_over_loop_hybrid_ratio": o1_median / hybrid_median,
            "compact_ea_vs_baseline_ratio": statistics.median(sample_values["S3_O1_BASELINE"]) / statistics.median(sample_values["S3_O1_COMPACT_EA"]),
            "compact_ea_applied": compact_applied,
            "compact_ea_decisions": function_summary,
            "binary_metrics": binaries,
            "static_ir_metrics": {
                label: candidate["assembly_opcode_counts"]
                for label, candidate in implementations.items()
                if label.startswith("S3_")
            },
        }

    host = json.loads(_run(["python3", "-c", "import json,platform,sys; print(json.dumps({'python':sys.version.split()[0],'platform':platform.platform(),'machine':platform.machine()}))"]))
    cpu_model = next(
        (line.partition(":")[2].strip() for line in _run(["lscpu"]).splitlines() if line.startswith("Model name:")),
        "unknown",
    )
    size_version = _run(["size", "--version"]).splitlines()[0]
    objdump_version = _run(["objdump", "--version"]).splitlines()[0]
    source_identity = _source_provenance(source_revision, source_tree, source_worktree_state)
    return {
        "schema_version": "1.0.0",
        "campaign": "S3_1_5_REAL_WORLD_COMPUTE_QUALIFICATION_AND_NATIVE_GAP_CLOSURE",
        "started_at_utc": started_at_utc,
        "source_revision": source_identity,
        "host": host,
        "cpu_model": cpu_model,
        "hardware_counter_capability": _perf_capability(),
        "tools": {"size": size_version, "objdump": objdump_version},
        "protocol": {
            "c_flags": ["-O1", "-fno-fast-math", "-ffp-contract=off", "-fno-tree-vectorize"],
            "s3_optimization_levels": ["O0", "O1"],
            "s3_native_policies": ["baseline", "compact-ea experimental"],
            "instruction_budget_modes": ["per-instruction", "exact-segment", "loop-hybrid"],
            "default_instruction_budget_mode": "per-instruction",
            "max_s3_instructions": MAX_INSTRUCTIONS,
            "simd": "not enabled; scalar C vectorization disabled for this comparison",
        },
        "candidate_artifacts": {
            label: {
                key: (str(value) if isinstance(value, Path) else value)
                for key, value in candidate.items()
                if key not in {"assembly_opcode_counts"}
            }
            for label, candidate in compiler_candidates.items()
        },
        "compiler_source_sha256": {
            path.relative_to(ROOT).as_posix(): _sha256(path.read_bytes())
            for path in (
                ROOT / "bootstrap/s3/optimizer.py",
                ROOT / "bootstrap/s3/memory_effects.py",
                ROOT / "bootstrap/s3/backends/x86_64/backend.py",
                ROOT / "bootstrap/s3/backends/x86_64/emitter.py",
                ROOT / "bootstrap/s3/codegen.py",
            )
        },
        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        "workloads": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--source-revision")
    parser.add_argument("--source-tree")
    parser.add_argument("--source-worktree-state", choices=("clean", "dirty"))
    args = parser.parse_args()
    result = run(
        args.output_dir,
        iterations=args.iterations,
        warmups=args.warmups,
        samples=args.samples,
        source_revision=args.source_revision,
        source_tree=args.source_tree,
        source_worktree_state=args.source_worktree_state,
    )
    output = args.output_dir / "native-workload-benchmark-v1.json"
    output.write_bytes(_json_bytes(result))
    print(f"BENCHMARK_JSON={output}")
    for workload_id, data in result["workloads"].items():
        print(
            f"{workload_id} S3_O1/C_O1={data['o1_s3_over_c_ratio']:.4f}x "
            f"PER/EXACT={data['per_over_exact_segment_ratio']:.4f}x "
            f"PER/HYBRID={data['per_over_loop_hybrid_ratio']:.4f}x "
            f"compact_applied={data['compact_ea_applied']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
