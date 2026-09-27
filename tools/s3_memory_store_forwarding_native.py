"""Paired Linux native characterization for the S3 1.10 research transform."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import platform
import random
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.backends.x86_64 import NativeToolchain, generate_ffi_assembly  # noqa: E402
from bootstrap.s3.codegen import generate_assembly  # noqa: E402
from bootstrap.s3.optimizer import OptimizationLevel  # noqa: E402
from bootstrap.s3.pipeline import compile_source  # noqa: E402
from tools import s3_15_native_workload_benchmark as benchmark  # noqa: E402
from tools.s3_memory_availability_experiment import forward_available_stores  # noqa: E402
from tools.s3_memory_repeated_load_experiment import (  # noqa: E402
    forward_available_loads,
    forward_available_loads_by_ssa_substitution,
)
from tools.s3_memory_load_reuse_discovery import (  # noqa: E402
    DEFAULT_PROFILE as DYNAMIC_PROFILE,
    _profile_block_visits,
)
from bootstrap.s3.memory_value_availability import (  # noqa: E402
    analyze_repeated_load_availability,
)
from bootstrap.s3.ssa import SSABuilder  # noqa: E402


SEED = 3110
WORKLOAD_SYMBOLS = {
    "engineering.point-cloud-summary.v1": "point_cloud_summary",
    "geospatial.raster-window-statistics.v1": "raster_window_statistics",
    "energy.pv-timeseries-aggregation.v1": "energy_series_aggregation",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _compile(program, output: Path, assembly_path: Path) -> tuple[dict[str, object], object]:
    assembly = generate_ffi_assembly(
        program,
        max_instructions=benchmark.MAX_INSTRUCTIONS,
    )
    toolchain = NativeToolchain.detect()
    toolchain.build_shared(assembly, output, keep_assembly=assembly_path)
    function = next(item for item in program.functions if item.name in WORKLOAD_SYMBOLS.values())
    counts = Counter(instruction.opcode.value for instruction in function.instructions)
    return (
        {
            "shared_object_sha256": _sha256(output.read_bytes()),
            "assembly_sha256": _sha256(assembly.encode()),
            "assembly_bytes": len(assembly.encode()),
            "assembly_instruction_count": len(function.instructions),
            "assembly_opcode_counts": dict(sorted(counts.items())),
            "binary": benchmark._binary_metrics(output, function.name),
        },
        output,
    )


def _run(
    output_dir: Path,
    *,
    samples: int,
    iterations: int,
    warmups: int,
    experiment: str = "store-load",
) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("native memory experiment requires Linux x86-64")
    if samples < 3 or iterations < 1 or warmups < 1:
        raise ValueError("samples must be >= 3 and iterations/warmups must be positive")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest, references = benchmark._load_inputs()
    manifest_by_id = {row["workload_id"]: row for row in manifest["workloads"]}
    rows: dict[str, object] = {}
    toolchain = NativeToolchain.detect()
    if experiment == "store-load":
        transform = forward_available_stores
        experiment_id = "EXP-S3-110-STORE-LOAD-001"
        transform_description = "proof-gated cross-block STORE-to-LOAD forwarding"
    elif experiment == "load-load":
        transform = forward_available_loads
        experiment_id = "EXP-S3-110-LOAD-001"
        transform_description = "proof-gated cross-block exact-cell LOAD reuse"
    elif experiment == "load-load-ssa-substitution":
        transform = forward_available_loads_by_ssa_substitution
        experiment_id = "EXP-S3-110-LOAD-SSA-001"
        transform_description = "proof-gated cross-block LOAD removal by dominating SSA value substitution"
    elif experiment == "load-load-hot":
        transform = forward_available_loads
        experiment_id = "EXP-S3-110-LOAD-HOT-001"
        transform_description = "proof-gated cross-block LOAD reuse limited to profiled nonzero blocks"
    else:
        raise ValueError(f"unsupported memory transformation experiment: {experiment}")
    profile_results = None
    if experiment == "load-load-hot":
        profile_bytes = DYNAMIC_PROFILE.read_bytes()
        profile = json.loads(profile_bytes)
        profile_results = profile.get("results")
        if not isinstance(profile_results, dict):
            raise ValueError("dynamic profile lacks workload results")

    for workload in references["workloads"]:
        workload_id = workload["workload_id"]
        manifest_row = manifest_by_id[workload_id]
        if workload["dataset_sha256"] != manifest_row["dataset_sha256"]:
            raise ValueError(f"{workload_id} dataset digest differs from manifest")
        if workload["output_sha256"] != manifest_row["expected_output_sha256"]:
            raise ValueError(f"{workload_id} expected-output digest differs from manifest")

        source_path = ROOT / "benchmarks" / manifest_row["s3_source"]
        source_bytes = source_path.read_bytes()
        source = source_bytes.decode("utf-8")
        baseline_compilation = compile_source(source, OptimizationLevel.O1)
        baseline_ir, baseline_assembly = baseline_compilation.require_ordinary_artifacts()
        if experiment == "load-load-hot":
            profile_result = profile_results[workload_id]
            visits = _profile_block_visits(profile_result)
            selected_sites = {
                (function.name, candidate.block, candidate.instruction_index)
                for function in baseline_ir.functions
                if not function.external
                for candidate in analyze_repeated_load_availability(
                    SSABuilder.build_function(function)
                ).candidates
                if candidate.cross_block_available
                and visits.get((function.name, candidate.block), 0) > 0
            }
            if profile_result.get("source_sha256") != _sha256(source_bytes.replace(b"\r\n", b"\n")):
                raise ValueError(f"{workload_id}: source SHA differs from dynamic profile")
            candidate_ir, forwarded = transform(
                baseline_ir, selected_sites=selected_sites
            )
        else:
            candidate_ir, forwarded = transform(baseline_ir)
        candidate_assembly = generate_assembly(candidate_ir)

        paths = {
            "baseline": (output_dir / f"{workload_id}-baseline.so", output_dir / f"{workload_id}-baseline.s"),
            "candidate": (output_dir / f"{workload_id}-candidate.so", output_dir / f"{workload_id}-candidate.s"),
        }
        baseline_info, baseline_path = _compile(
            baseline_assembly, paths["baseline"][0], paths["baseline"][1]
        )
        candidate_info, candidate_path = _compile(
            candidate_assembly, paths["candidate"][0], paths["candidate"][1]
        )

        output_count = len(benchmark.OUTPUT_KEYS[workload_id])
        output_type = ctypes.c_double * output_count
        baseline_output = output_type()
        candidate_output = output_type()
        baseline_library = ctypes.CDLL(str(baseline_path))
        candidate_library = ctypes.CDLL(str(candidate_path))
        baseline_call = benchmark._make_call(baseline_library, workload, baseline_output)
        candidate_call = benchmark._make_call(candidate_library, workload, candidate_output)
        baseline_status = baseline_call()
        candidate_status = candidate_call()
        if baseline_status != 0 or candidate_status != 0:
            raise RuntimeError(f"{workload_id} correctness call failed: {baseline_status}/{candidate_status}")
        baseline_values = list(baseline_output)
        candidate_values = list(candidate_output)
        benchmark._check_output(baseline_values, workload["expected_output"], workload_id)
        benchmark._check_output(candidate_values, workload["expected_output"], workload_id)
        if baseline_values != candidate_values:
            raise AssertionError(f"{workload_id} candidate differs from baseline native output")
        output_digest = _sha256(_json_bytes([round(value, 10) for value in candidate_values]))

        for _ in range(warmups):
            if baseline_call() != 0 or candidate_call() != 0:
                raise RuntimeError(f"{workload_id} failed during warmup")
        timings: dict[str, list[float]] = {"baseline": [], "candidate": []}
        order_rows: list[list[str]] = []
        for sample_index in range(samples):
            order = ["baseline", "candidate"]
            if (sample_index + SEED) % 2:
                order.reverse()
            order_rows.append(order)
            for label in order:
                call = baseline_call if label == "baseline" else candidate_call
                timings[label].append(benchmark._measure(call, iterations))

        median_baseline = statistics.median(timings["baseline"])
        median_candidate = statistics.median(timings["candidate"])
        ratio = median_baseline / median_candidate
        rows[workload_id] = {
            "source_path": manifest_row["s3_source"],
            "source_sha256": _sha256(source_bytes),
            "dataset_sha256": workload["dataset_sha256"],
            "correctness": "PASS_REFERENCE_AND_EXACT_BASELINE_OUTPUT",
            "candidate_output_sha256": output_digest,
            "eligible_loads_forwarded": forwarded,
            "eligible_loads_transformed": forwarded,
            "baseline": baseline_info,
            "candidate": candidate_info,
            "timing": {
                "class": "CHARACTERIZATION_ONLY",
                "native_speedup_claim": False,
                "scope": "same-process scalar C ABI; setup and compilation excluded; ctypes dispatch included equally",
                "samples": samples,
                "iterations_per_sample": iterations,
                "warmups": warmups,
                "order_seed": SEED,
                "paired_order": order_rows,
                "baseline_ns_per_call": timings["baseline"],
                "candidate_ns_per_call": timings["candidate"],
                "baseline_median_ns_per_call": median_baseline,
                "candidate_median_ns_per_call": median_candidate,
                "baseline_over_candidate_median_ratio": ratio,
            },
        }

    return {
        "schema_version": "1.0.0",
        "experiment_id": experiment_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "native_compiler": toolchain.compiler,
            "native_compiler_version": benchmark._run(
                [toolchain.compiler, "--version"]
            ).splitlines()[0],
            "pmu": benchmark._perf_capability(),
            "correctness_before_timing": True,
            "control": "O1 compiler output",
            "candidate": f"O1 IR with experimental {transform_description}",
            "transformation_in_production_pipeline": False,
            "dynamic_profile_sha256": (
                _sha256(DYNAMIC_PROFILE.read_bytes())
                if experiment == "load-load-hot"
                else None
            ),
        },
        "workloads": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=21)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument(
        "--experiment",
        choices=(
            "store-load",
            "load-load",
            "load-load-hot",
            "load-load-ssa-substitution",
        ),
        default="store-load",
    )
    args = parser.parse_args()
    result = _run(
        args.output.parent,
        samples=args.samples,
        iterations=args.iterations,
        warmups=args.warmups,
        experiment=args.experiment,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_json_bytes(result))
    print(f"EXPERIMENT={result['experiment_id']}")
    print(f"OUTPUT={args.output}")
    for workload_id, row in result["workloads"].items():
        timing = row["timing"]
        print(
            f"{workload_id}: forwarded={row['eligible_loads_forwarded']} "
            f".text={row['baseline']['binary']['text_section_bytes']}->"
            f"{row['candidate']['binary']['text_section_bytes']} "
            f"instructions={row['baseline']['binary']['static_machine_instructions']}->"
            f"{row['candidate']['binary']['static_machine_instructions']} "
            f"median_ns={timing['baseline_median_ns_per_call']:.3f}->"
            f"{timing['candidate_median_ns_per_call']:.3f} ratio={timing['baseline_over_candidate_median_ratio']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
