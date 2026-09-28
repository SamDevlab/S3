"""Count research candidate TMOVs by their allocator-assigned locations."""

from __future__ import annotations

import argparse
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

from bootstrap.s3.assembly import AssemblyFunction, AssemblyOpcode
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from tools import s3_15_native_workload_benchmark as benchmark
from tools.s3_memory_availability_experiment import forward_available_stores
from tools.s3_memory_repeated_load_experiment import (
    forward_available_loads_by_ssa_substitution,
)

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


def summarize_move_locations(function: AssemblyFunction) -> dict[str, Any]:
    # The pinned workloads use PER, which reserves r15 in the real codegen path.
    allocation = analyze_allocation(function, reserved_registers=frozenset({"r15"}))
    categories: Counter[str] = Counter()
    sites: list[dict[str, Any]] = []
    for block in function.blocks:
        for index, instruction in enumerate(block.instructions):
            if instruction.opcode is not AssemblyOpcode.TMOV:
                continue
            if len(instruction.registers) != 2:
                raise ValueError("TMOV must have exactly destination and source")
            destination, source = instruction.registers
            destination_location = allocation.physical_register(destination)
            source_location = allocation.physical_register(source)
            if destination == source:
                category = "SAME_VIRTUAL_REGISTER"
            elif destination_location is None and source_location is None:
                category = "BOTH_STACK_RESIDENT"
            elif destination_location is None:
                category = "DESTINATION_STACK_SOURCE_REGISTER"
            elif source_location is None:
                category = "SOURCE_STACK_DESTINATION_REGISTER"
            elif destination_location == source_location:
                category = "SAME_PHYSICAL_REGISTER"
            else:
                category = "DISTINCT_PHYSICAL_REGISTERS"
            categories[category] += 1
            sites.append(
                {
                    "block": block.label,
                    "instruction_index": index,
                    "destination_vreg": destination,
                    "source_vreg": source,
                    "destination_location": destination_location or "STACK",
                    "source_location": source_location or "STACK",
                    "location_relation": category,
                }
            )
    return {
        "tmov_count": len(sites),
        "allocated_same_physical_count": categories["SAME_PHYSICAL_REGISTER"],
        "location_relation_counts": dict(sorted(categories.items())),
        "candidate_sites": sites,
        "interpretation": (
            "Static allocation-location classification only. Same-register sites are "
            "potential emitter simplifications, not proof of removable logical budget "
            "work; stack and distinct-register copies are not candidates for omission."
        ),
    }


def run(*, root: Path) -> dict[str, Any]:
    manifest, references = benchmark._load_inputs()
    manifest_by_id = {row["workload_id"]: row for row in manifest["workloads"]}
    workloads: list[dict[str, Any]] = []
    for reference in sorted(references["workloads"], key=lambda row: row["workload_id"]):
        workload_id = reference["workload_id"]
        source_path = root / "benchmarks" / manifest_by_id[workload_id]["s3_source"]
        source_bytes = source_path.read_bytes().replace(b"\r\n", b"\n")
        if b"\r" in source_bytes:
            raise ValueError(f"{workload_id}: noncanonical CR bytes")
        source_sha = _sha(source_bytes)
        if source_sha != reference.get("source_sha256", source_sha):
            raise ValueError(f"{workload_id}: source identity mismatch")
        compilation = compile_source(source_bytes.decode("utf-8"), OptimizationLevel.O1)
        module, baseline_program = compilation.require_ordinary_artifacts()
        ssa_module, _ = forward_available_loads_by_ssa_substitution(module)
        store_module, _ = forward_available_stores(module)
        programs = {
            "baseline": baseline_program,
            "ssa_substitution": generate_assembly(ssa_module),
            "store_to_load": generate_assembly(store_module),
        }
        symbol = WORKLOAD_SYMBOLS[workload_id]
        candidates = []
        for candidate, program in programs.items():
            function = next(item for item in program.functions if item.name == symbol)
            candidates.append(
                {"candidate": candidate, **summarize_move_locations(function)}
            )
        workloads.append(
            {
                "workload_id": workload_id,
                "source_sha256": source_sha,
                "function_symbol": symbol,
                "candidates": candidates,
            }
        )
    return {
        "schema_version": "1.0.0",
        "experiment_id": "EXP-S3-111-MOVE-COALESCE-001",
        "classification": "ALLOCATOR_LOCATION_ELIGIBILITY_SCAN_NO_TRANSFORMATION",
        "provenance": {
            "s3_commit": _git(root, "rev-parse", "HEAD"),
            "s3_tree": _git(root, "rev-parse", "HEAD^{tree}"),
            "compiler_source_dirty": bool(_git(root, "status", "--porcelain", "--", "bootstrap/s3")),
            "tool_sha256": _sha(Path(__file__).read_bytes()),
            "target_host": f"{platform.system()} {platform.machine()}",
            "optimization": "O1",
        },
        "native_build": "NOT_PERFORMED",
        "timing": "NOT_MEASURED",
        "allocation_policy": "PER instruction budget; r15 reserved, matching pinned O1 codegen",
        "workloads": workloads,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(root=args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    counts = {
        row["candidate"]: sum(candidate["tmov_count"] for workload in result["workloads"] for candidate in workload["candidates"] if candidate["candidate"] == row["candidate"])
        for row in result["workloads"][0]["candidates"]
    }
    print(json.dumps({"experiment_id": result["experiment_id"], "tmov_by_candidate": counts, "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
