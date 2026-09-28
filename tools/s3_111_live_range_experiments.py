"""Bounded CFG-aware liveness characterization for S3 1.11 candidates."""

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

from bootstrap.s3.assembly import AssemblyFunction
from bootstrap.s3.backends.x86_64.liveness import analyze_liveness
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


def summarize_liveness(function: AssemblyFunction) -> dict[str, Any]:
    """Summarize live-boundary incidence without inventing cross-block order."""
    result = analyze_liveness(function)
    use_counts: Counter[int] = Counter()
    def_counts: Counter[int] = Counter()
    register_blocks: dict[int, set[str]] = {}
    register_live_boundaries: Counter[int] = Counter()
    block_rows: list[dict[str, Any]] = []
    total_boundaries = 0
    peak_live = 0

    for block in function.blocks:
        row = result.blocks[block.label]
        boundary_sets: list[frozenset[int]] = []
        for instruction_row in row.instructions:
            use_counts.update(instruction_row.uses)
            def_counts.update(instruction_row.defs)
            boundary_sets.extend((instruction_row.live_before, instruction_row.live_after))
        live_sizes = [len(live) for live in boundary_sets]
        peak_live = max(peak_live, max(live_sizes, default=0))
        total_boundaries += sum(live_sizes)

        positions: dict[int, list[int]] = {}
        for boundary_index, live in enumerate(boundary_sets):
            for register in live:
                positions.setdefault(register, []).append(boundary_index)
                register_blocks.setdefault(register, set()).add(block.label)
                register_live_boundaries[register] += 1

        block_rows.append(
            {
                "label": block.label,
                "instruction_count": len(block.instructions),
                "live_in_count": len(row.live_in),
                "live_out_count": len(row.live_out),
                "peak_live": max(live_sizes, default=0),
                "live_boundary_incidence": sum(live_sizes),
                "live_register_count": len(positions),
                "max_within_block_boundary_span": max(
                    (indexes[-1] - indexes[0] + 1 for indexes in positions.values()),
                    default=0,
                ),
            }
        )

    registers = sorted(set(use_counts) | set(def_counts) | set(register_live_boundaries))
    live_counts = [register_live_boundaries[register] for register in registers]
    return {
        "function": function.name,
        "block_count": len(function.blocks),
        "instruction_count": len(function.instructions),
        "register_count_observed": len(registers),
        "total_live_boundary_incidence": total_boundaries,
        "peak_live_virtual_registers": peak_live,
        "register_use_sites": sum(use_counts.values()),
        "register_def_sites": sum(def_counts.values()),
        "registers_live_across_multiple_blocks": sum(
            len(register_blocks.get(register, ())) > 1 for register in registers
        ),
        "live_boundary_incidence_by_register": [
            {
                "register": register,
                "live_boundaries": register_live_boundaries[register],
                "blocks": len(register_blocks.get(register, ())),
                "use_sites": use_counts[register],
                "def_sites": def_counts[register],
            }
            for register in registers
        ],
        "blocks": block_rows,
        "metric_contract": (
            "CFG-aware liveness sets; positions are ordered only within each block. "
            "Boundary incidence and per-block spans are static analysis metrics, "
            "not dynamic frequency, runtime cost, or a global linear live-range length."
        ),
    }


def _candidate_programs(module: Any, baseline: Any) -> dict[str, Any]:
    ssa_module, _ = forward_available_loads_by_ssa_substitution(module)
    store_module, _ = forward_available_stores(module)
    return {
        "baseline": baseline,
        "ssa_substitution": generate_assembly(ssa_module),
        "store_to_load": generate_assembly(store_module),
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
            raise ValueError(f"{workload_id}: noncanonical CR bytes in source")
        source_sha = _sha(source_bytes)
        if source_sha != reference.get("source_sha256", source_sha):
            raise ValueError(f"{workload_id}: source identity mismatch")

        compilation = compile_source(source_bytes.decode("utf-8"), OptimizationLevel.O1)
        module, baseline_program = compilation.require_ordinary_artifacts()
        symbol = WORKLOAD_SYMBOLS[workload_id]
        rows = []
        for candidate_name, program in _candidate_programs(module, baseline_program).items():
            function = next(item for item in program.functions if item.name == symbol)
            rows.append({"candidate": candidate_name, **summarize_liveness(function)})
        baseline = next(row for row in rows if row["candidate"] == "baseline")
        for row in rows:
            row["delta_from_baseline"] = {
                key: row[key] - baseline[key]
                for key in (
                    "instruction_count",
                    "register_count_observed",
                    "total_live_boundary_incidence",
                    "peak_live_virtual_registers",
                    "registers_live_across_multiple_blocks",
                )
            }
        workloads.append(
            {
                "workload_id": workload_id,
                "source_sha256": source_sha,
                "function_symbol": symbol,
                "candidates": rows,
            }
        )

    return {
        "schema_version": "1.0.0",
        "experiment_id": "EXP-S3-111-LIVE-001",
        "classification": "STATIC_CFG_LIVENESS_CHARACTERIZATION_NO_TRANSFORM_PROMOTION",
        "provenance": {
            "s3_commit": _git(root, "rev-parse", "HEAD"),
            "s3_tree": _git(root, "rev-parse", "HEAD^{tree}"),
            "compiler_source_dirty": bool(_git(root, "status", "--porcelain", "--", "bootstrap/s3")),
            "tool_sha256": _sha(Path(__file__).read_bytes()),
            "target_host": f"{platform.system()} {platform.machine()}",
            "optimization": "O1",
        },
        "timing": "NOT_MEASURED",
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
    print(json.dumps({"experiment_id": result["experiment_id"], "workloads": len(result["workloads"]), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
