"""Compare static allocator/codegen facts for S3 1.10 memory experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.backends.x86_64 import generate_ffi_assembly  # noqa: E402
from bootstrap.s3.codegen import generate_assembly  # noqa: E402
from bootstrap.s3.codegen_report import build_codegen_report  # noqa: E402
from bootstrap.s3.memory_value_availability import (  # noqa: E402
    analyze_repeated_load_availability,
)
from bootstrap.s3.optimizer import OptimizationLevel  # noqa: E402
from bootstrap.s3.pipeline import compile_source  # noqa: E402
from bootstrap.s3.ssa import SSABuilder  # noqa: E402
from tools import s3_15_native_workload_benchmark as benchmark  # noqa: E402
from tools.s3_memory_availability_experiment import forward_available_stores  # noqa: E402
from tools.s3_memory_load_reuse_discovery import (  # noqa: E402
    DEFAULT_PROFILE,
    _profile_block_visits,
)
from tools.s3_memory_repeated_load_experiment import (  # noqa: E402
    forward_available_loads,
    forward_available_loads_by_ssa_substitution,
)


DEFAULT_OUTPUT = (
    ROOT
    / "reports/s3-1.10-memory-intelligence-value-locality/evidence"
    / "EXP-S3-110-ALLOCATOR-EFFECT-001.json"
)
MAX_INSTRUCTIONS = 1_000_000_000
WORKLOAD_SYMBOLS = {
    "engineering.point-cloud-summary.v1": "point_cloud_summary",
    "geospatial.raster-window-statistics.v1": "raster_window_statistics",
    "energy.pv-timeseries-aggregation.v1": "energy_series_aggregation",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _allocator_facts(program, symbol: str, source_sha256: str) -> dict[str, object]:
    native_assembly = generate_ffi_assembly(
        program, max_instructions=MAX_INSTRUCTIONS
    )
    report = build_codegen_report(
        program,
        native_assembly,
        source_sha256=source_sha256,
        optimization="O1",
        max_frames=1024,
        max_instructions=MAX_INSTRUCTIONS,
    )
    function = next(row for row in report["functions"] if row["name"] == symbol)
    assembly_function = next(
        item for item in program.functions if item.name == symbol
    )
    instruction_counts: dict[str, int] = {}
    for block in assembly_function.blocks:
        for instruction in block.instructions:
            instruction_counts[instruction.opcode.value] = (
                instruction_counts.get(instruction.opcode.value, 0) + 1
            )
    return {
        "assembly_instruction_count": function["assembly_instruction_count"],
        "assembly_opcode_counts": dict(sorted(instruction_counts.items())),
        "generated_native_assembly": function["native_assembly"],
        "frame_bytes": function["frame_bytes"],
        "allocation": {
            key: function["allocation"][key]
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
    }


def _run() -> dict[str, object]:
    manifest, references = benchmark._load_inputs()
    manifest_by_id = {row["workload_id"]: row for row in manifest["workloads"]}
    profile_bytes = DEFAULT_PROFILE.read_bytes()
    profile = json.loads(profile_bytes)
    profile_results = profile["results"]
    workloads: dict[str, object] = {}

    for workload in references["workloads"]:
        workload_id = workload["workload_id"]
        source_path = ROOT / "benchmarks" / manifest_by_id[workload_id]["s3_source"]
        checkout_bytes = source_path.read_bytes()
        source_bytes = checkout_bytes.replace(b"\r\n", b"\n")
        if b"\r" in source_bytes:
            raise ValueError(f"{workload_id}: non-canonical CR in source")
        source_sha = _sha256(source_bytes)
        if profile_results[workload_id].get("source_sha256") != source_sha:
            raise ValueError(f"{workload_id}: source identity differs from profile")
        source = source_bytes.decode("utf-8")
        compilation = compile_source(source, OptimizationLevel.O1)
        baseline_ir, baseline_program = compilation.require_ordinary_artifacts()
        visits = _profile_block_visits(profile_results[workload_id])

        hot_sites = {
            (function.name, candidate.block, candidate.instruction_index)
            for function in baseline_ir.functions
            if not function.external
            for candidate in analyze_repeated_load_availability(
                SSABuilder.build_function(function)
            ).candidates
            if candidate.cross_block_available
            and visits.get((function.name, candidate.block), 0) > 0
        }

        store_ir, _store_count = forward_available_stores(baseline_ir)
        all_load_ir, _all_load_count = forward_available_loads(baseline_ir)
        ssa_load_ir, ssa_load_count = forward_available_loads_by_ssa_substitution(
            baseline_ir
        )
        hot_load_ir, _hot_load_count = forward_available_loads(
            baseline_ir, selected_sites=hot_sites
        )
        candidates = {
            "baseline": baseline_program,
            "store_to_load_all_proven": generate_assembly(store_ir),
            "load_to_load_all_proven": generate_assembly(all_load_ir),
            "load_to_load_ssa_value_substitution": generate_assembly(ssa_load_ir),
            "load_to_load_profile_hot_only": generate_assembly(hot_load_ir),
        }
        symbol = WORKLOAD_SYMBOLS[workload_id]
        workloads[workload_id] = {
            "source_sha256": source_sha,
            "profiled_hot_repeated_load_sites": len(hot_sites),
            "ssa_value_substitution_forwarded_loads": ssa_load_count,
            "candidates": {
                label: _allocator_facts(program, symbol, source_sha)
                for label, program in candidates.items()
            },
        }

    return {
        "schema_version": "1.0.0",
        "experiment_id": "EXP-S3-110-ALLOCATOR-EFFECT-001",
        "classification": "STATIC_ALLOCATOR_AND_CODEGEN_PROBE_NOT_DYNAMIC_SPILL_OR_PERFORMANCE_EVIDENCE",
        "control": {
            "s3_commit": "e27dff1e712e50271df9f860669cd714e28f4ce7",
            "optimization": "O1",
            "dynamic_profile_sha256": _sha256(profile_bytes),
            "native_generation": "x86-64 FFI assembly text; no object built or executed by this probe",
        },
        "limits": {
            "dynamic_spills": "NOT_MEASURED",
            "stack_resident_values_are_spills": False,
            "logical_block_visits_are_hardware_counts": False,
        },
        "workloads": workloads,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = _run()
    encoded = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"OUTPUT={args.output}")
    print(f"OUTPUT_SHA256={_sha256(encoded)}")
    for workload_id, workload in result["workloads"].items():
        print(workload_id)
        for label, row in workload["candidates"].items():
            allocation = row["allocation"]
            print(
                f"  {label}: asm={row['assembly_instruction_count']} "
                f"vregs={allocation['virtual_register_count']} "
                f"stack_resident={allocation['stack_resident_virtual_register_count']} "
                f"peak_live={allocation['peak_live_virtual_registers']} "
                f"frame={row['frame_bytes']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
