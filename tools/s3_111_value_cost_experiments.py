"""Measure a research-only pressure guard for dominating SSA load reuse."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.backends.x86_64 import NativeToolchain, generate_ffi_assembly
from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.codegen_report import build_codegen_report
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from tools import s3_15_native_workload_benchmark as benchmark
from tools.s3_memory_availability_experiment import forward_available_stores
from tools.s3_memory_repeated_load_experiment import (
    forward_available_loads_by_ssa_substitution,
)

MAX_INSTRUCTIONS = 1_000_000_000
WORKLOAD_SYMBOLS = {
    "engineering.point-cloud-summary.v1": "point_cloud_summary",
    "geospatial.raster-window-statistics.v1": "raster_window_statistics",
    "energy.pv-timeseries-aggregation.v1": "energy_series_aggregation",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _codegen_facts(program: Any, symbol: str, source_sha: str) -> dict[str, Any]:
    native = generate_ffi_assembly(program, max_instructions=MAX_INSTRUCTIONS)
    report = build_codegen_report(
        program,
        native,
        source_sha256=source_sha,
        optimization="O1",
        max_frames=1024,
        max_instructions=MAX_INSTRUCTIONS,
    )
    row = next(item for item in report["functions"] if item["name"] == symbol)
    function = next(item for item in program.functions if item.name == symbol)
    opcode_counts: Counter[str] = Counter()
    for block in function.blocks:
        for instruction in block.instructions:
            opcode_counts[instruction.opcode.value] += 1
    allocation = row["allocation"]
    return {
        "assembly_instruction_count": row["assembly_instruction_count"],
        "assembly_opcode_counts": dict(sorted(opcode_counts.items())),
        "frame_bytes": row["frame_bytes"],
        "allocation": {
            key: allocation[key]
            for key in (
                "virtual_register_count",
                "physical_register_count",
                "stack_resident_virtual_register_count",
                "address_taken_virtual_register_count",
                "peak_live_virtual_registers",
                "assembly_move_count",
                "moves_assigned_same_physical_register",
                "dynamic_spills",
                "dynamic_spills_status",
            )
        },
        "native_assembly_source_sha256": _sha(native.encode()),
    }


def _compile_native(program: Any, output: Path) -> tuple[Path, str]:
    assembly = generate_ffi_assembly(program, max_instructions=MAX_INSTRUCTIONS)
    toolchain = NativeToolchain.detect()
    toolchain.build_shared(assembly, output, keep_assembly=output.with_suffix(".s"))
    return output, assembly


def _artifact_facts(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "file_name": path.name,
        "bytes": len(data),
        "sha256": _sha(data),
    }


def _check_guard(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    baseline_binary: dict[str, Any] | None = None,
    candidate_binary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base, after = baseline["allocation"], candidate["allocation"]
    peak_delta = after["peak_live_virtual_registers"] - base["peak_live_virtual_registers"]
    stack_delta = (
        after["stack_resident_virtual_register_count"]
        - base["stack_resident_virtual_register_count"]
    )
    pressure_accepts = peak_delta <= 0 and stack_delta <= 0
    result: dict[str, Any] = {
        "peak_live_delta": peak_delta,
        "stack_resident_virtual_delta": stack_delta,
        "accept_if_peak_live_nonincreasing": peak_delta <= 0,
        "accept_if_stack_resident_nonincreasing": stack_delta <= 0,
        "pressure_guard_accepts": pressure_accepts,
        "policy": "require nonincreasing static peak-live and stack-resident counts",
    }
    if baseline_binary is None or candidate_binary is None:
        result["native_pareto_dominates"] = None
        result["adaptive_candidate_selected"] = pressure_accepts
        return result
    dimensions = (
        "text_section_bytes",
        "static_machine_instructions",
        "static_memory_references",
        "static_stack_references",
        "static_branches",
        "stack_frame_bytes",
    )
    deltas = {
        key: candidate_binary[key] - baseline_binary[key]
        for key in dimensions
    }
    dominates = all(delta <= 0 for delta in deltas.values()) and any(
        delta < 0 for delta in deltas.values()
    )
    result["native_metric_deltas"] = deltas
    result["native_pareto_dominates"] = dominates
    result["adaptive_candidate_selected"] = pressure_accepts and dominates
    result["multiobjective_policy"] = (
        "select only if peak-live and stack residency do not grow, all measured "
        "native dimensions are nonincreasing, and at least one native dimension improves"
    )
    return result


def run(output_dir: Path, *, root: Path, strategy: str = "ssa-substitution") -> dict[str, Any]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("native value-cost experiment requires Linux x86-64")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest, references = benchmark._load_inputs()
    manifest_by_id = {row["workload_id"]: row for row in manifest["workloads"]}
    workloads: list[dict[str, Any]] = []
    candidate_label = "ssa_substitution" if strategy == "ssa-substitution" else "store_to_load"

    for workload in sorted(references["workloads"], key=lambda row: row["workload_id"]):
        workload_id = workload["workload_id"]
        source_path = root / "benchmarks" / manifest_by_id[workload_id]["s3_source"]
        source_bytes = source_path.read_bytes().replace(b"\r\n", b"\n")
        if b"\r" in source_bytes:
            raise ValueError(f"{workload_id}: source contains noncanonical CR bytes")
        source_sha = _sha(source_bytes)
        if source_sha != workload.get("source_sha256", source_sha):
            raise ValueError(f"{workload_id}: reference source identity mismatch")

        compilation = compile_source(source_bytes.decode("utf-8"), OptimizationLevel.O1)
        module, baseline_program = compilation.require_ordinary_artifacts()
        if strategy == "ssa-substitution":
            candidate_module, eligible = forward_available_loads_by_ssa_substitution(module)
        elif strategy == "store-to-load":
            candidate_module, eligible = forward_available_stores(module)
        else:
            raise ValueError(f"unsupported transform strategy: {strategy}")
        candidate_program = generate_assembly(candidate_module)
        symbol = WORKLOAD_SYMBOLS[workload_id]
        baseline_facts = _codegen_facts(baseline_program, symbol, source_sha)
        candidate_facts = _codegen_facts(candidate_program, symbol, source_sha)
        baseline_path, _ = _compile_native(
            baseline_program, output_dir / f"{workload_id}-baseline.so"
        )
        candidate_path, _ = _compile_native(
            candidate_program, output_dir / f"{workload_id}-{candidate_label}.so"
        )
        output_rows: dict[str, dict[str, Any]] = {}
        calls: dict[str, Any] = {}
        libraries = {
            "baseline": ctypes.CDLL(str(baseline_path)),
            candidate_label: ctypes.CDLL(str(candidate_path)),
        }
        for label, library in libraries.items():
            output = (ctypes.c_double * len(benchmark.OUTPUT_KEYS[workload_id]))()
            call = benchmark._make_call(library, workload, output)
            status = call()
            if status != 0:
                raise RuntimeError(f"{workload_id} {label}: native status {status}")
            values = list(output)
            benchmark._check_output(values, workload["expected_output"], workload_id)
            encoded = benchmark._json_bytes([round(value, 10) for value in values])
            output_rows[label] = {"values": values, "output_sha256": _sha(encoded)}
            calls[label] = call
        if output_rows["baseline"]["output_sha256"] != output_rows[candidate_label]["output_sha256"]:
            raise RuntimeError(f"{workload_id}: native baseline and candidate outputs differ")

        baseline_binary = benchmark._binary_metrics(baseline_path, symbol)
        candidate_binary = benchmark._binary_metrics(candidate_path, symbol)
        guard = _check_guard(
            baseline_facts, candidate_facts, baseline_binary, candidate_binary
        )
        samples: dict[str, list[float]] = {"baseline": [], candidate_label: []}
        for _ in range(benchmark.DEFAULT_WARMUPS):
            calls["baseline"]()
            calls[candidate_label]()
        order = ["baseline", candidate_label]
        for index in range(benchmark.DEFAULT_SAMPLES):
            if index % 2:
                order.reverse()
            for label in order:
                samples[label].append(
                    benchmark._measure(calls[label], benchmark.DEFAULT_ITERATIONS)
                )
        timing = benchmark._paired_ratio_summary(
            samples["baseline"], samples[candidate_label], seed=11110 + len(workloads)
        )

        workloads.append(
            {
                "workload_id": workload_id,
                "source_path": str(source_path.relative_to(root)).replace("\\", "/"),
                "source_sha256": source_sha,
                "eligible_sites_forwarded": eligible,
                "correctness": "PASS_REFERENCE_AND_NATIVE_OUTPUT_EQUAL",
                "native_output": output_rows,
                "pressure_guard": guard,
                "static_codegen": {
                    "baseline": baseline_facts,
                    candidate_label: candidate_facts,
                },
                "native_binary": {
                    "baseline": baseline_binary,
                    candidate_label: candidate_binary,
                    "delta": {
                        key: candidate_binary[key] - baseline_binary[key]
                        for key in (
                            "text_section_bytes",
                            "static_machine_instructions",
                            "static_memory_references",
                            "static_stack_references",
                            "static_branches",
                            "stack_frame_bytes",
                        )
                    },
                },
                "native_artifacts": {
                    "baseline": _artifact_facts(baseline_path),
                    candidate_label: _artifact_facts(candidate_path),
                },
                "timing": {
                    "baseline": benchmark._summary(samples["baseline"]),
                    candidate_label: benchmark._summary(samples[candidate_label]),
                    "raw_samples_ns_per_call": {
                        "baseline": samples["baseline"],
                        candidate_label: samples[candidate_label],
                    },
                    "paired_baseline_over_candidate": timing,
                    "classification": timing["classification"],
                },
            }
        )

    return {
        "schema_version": "1.0.0",
        "experiment_id": (
            "EXP-S3-111-VALUE-COST-001"
            if strategy == "ssa-substitution"
            else "EXP-S3-111-VALUE-COST-002"
        ),
        "classification": "RESEARCH_ONLY_NATIVE_CHARACTERIZATION_NO_PIPELINE_PROMOTION",
        "control": {
            "s3_commit": _git(root, "rev-parse", "HEAD"),
            "s3_tree": _git(root, "rev-parse", "HEAD^{tree}"),
            "worktree_dirty": bool(_git(root, "status", "--porcelain")),
            "compiler_source_dirty": bool(_git(root, "diff", "--name-only", "HEAD", "--", "bootstrap/s3")),
            "experiment_tool_sha256": _sha(Path(__file__).read_bytes()),
            "optimization": "O1",
            "instruction_budget_mode": "PER",
            "native_target": "Linux x86-64",
            "toolchain": NativeToolchain.detect().compiler,
            "hardware_counters": {
                "status": "UNAVAILABLE_BY_POLICY",
                "perf_event_paranoid": "4",
                "source": "single baseline capability probe on the same Linux host",
            },
        },
        "protocol": {
            "warmups": benchmark.DEFAULT_WARMUPS,
            "samples": benchmark.DEFAULT_SAMPLES,
            "iterations_per_sample": benchmark.DEFAULT_ITERATIONS,
            "paired_order": "alternating baseline/candidate; reverse on odd sample",
            "timing_class": "CHARACTERIZATION_ONLY",
            "native_speedup_claim": False,
        },
        "transform": {
            "name": (
                "dominating exact-cell repeated-load SSA substitution"
                if strategy == "ssa-substitution"
                else "proof-gated exact-cell STORE-to-LOAD forwarding"
            ),
            "implementation": "existing proof-gated research helper; no production optimizer wiring",
            "cost_model": "non-scalar Pareto constraints over static pressure and native object dimensions",
        },
        "workloads": workloads,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--strategy", choices=("ssa-substitution", "store-to-load"),
        default="ssa-substitution",
    )
    args = parser.parse_args()
    result = run(args.output_dir, root=args.root.resolve(), strategy=args.strategy)
    encoded = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"OUTPUT={args.output}")
    print(f"OUTPUT_SHA256={_sha(encoded)}")
    for row in result["workloads"]:
        delta = row["native_binary"]["delta"]
        print(
            f"{row['workload_id']}: sites={row['eligible_sites_forwarded']} "
            f"selected={row['pressure_guard']['adaptive_candidate_selected']} "
            f"memory_delta={delta['static_memory_references']} "
            f"text_delta={delta['text_section_bytes']} "
            f"timing={row['timing']['classification']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
