"""Reproducible, diagnostic census of cross-block exact-cell repeated loads."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.memory_value_availability import (  # noqa: E402
    analyze_repeated_load_availability,
)
from bootstrap.s3.optimizer import OptimizationLevel  # noqa: E402
from bootstrap.s3.pipeline import compile_source  # noqa: E402
from bootstrap.s3.ssa import SSABuilder  # noqa: E402
from tools import s3_15_native_workload_benchmark as benchmark  # noqa: E402


DEFAULT_PROFILE = (
    ROOT
    / "reports/s3-1.9-native-observatory-optimization-discovery/evidence"
    / "profiling/logical-dynamic-profile-v3.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "reports/s3-1.10-memory-intelligence-value-locality/evidence"
    / "EXP-S3-110-LOAD-001.json"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _profile_block_visits(result: dict[str, object]) -> dict[tuple[str, str], int]:
    rows = result.get("hot_blocks")
    if not isinstance(rows, list):
        raise ValueError("profile lacks hot_blocks list")
    visits: dict[tuple[str, str], int] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("profile hot block row is not an object")
        function = row.get("function")
        block = row.get("block")
        count = row.get("logical_block_executions")
        if (
            not isinstance(function, str)
            or not isinstance(block, str)
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 0
        ):
            raise ValueError("profile hot block row has invalid identity/count")
        key = (function, block)
        if key in visits:
            raise ValueError(f"duplicate profile block identity: {key}")
        visits[key] = count
    return visits


def _run(profile_path: Path) -> dict[str, object]:
    manifest, references = benchmark._load_inputs()
    manifest_by_id = {row["workload_id"]: row for row in manifest["workloads"]}
    profile_bytes = profile_path.read_bytes()
    profile = json.loads(profile_bytes)
    results = profile.get("results")
    if not isinstance(results, dict):
        raise ValueError("dynamic profile has no results object")

    workloads: dict[str, object] = {}
    for workload in references["workloads"]:
        workload_id = workload["workload_id"]
        manifest_row = manifest_by_id[workload_id]
        source_path = ROOT / "benchmarks" / manifest_row["s3_source"]
        checkout_bytes = source_path.read_bytes()
        source_bytes = checkout_bytes.replace(b"\r\n", b"\n")
        if b"\r" in source_bytes:
            raise ValueError(f"{workload_id}: source contains non-canonical CR bytes")
        source_sha = _sha256(source_bytes)
        source = source_bytes.decode("utf-8")
        profile_result = results[workload_id]
        if profile_result.get("source_sha256") != source_sha:
            raise ValueError(f"{workload_id}: source SHA differs from pinned profile")
        if profile_result.get("dataset_sha256") != workload["dataset_sha256"]:
            raise ValueError(f"{workload_id}: dataset SHA differs from references")
        visits = _profile_block_visits(profile_result)

        compilation = compile_source(source, OptimizationLevel.O1)
        module, _assembly = compilation.require_ordinary_artifacts()
        function_rows: list[dict[str, object]] = []
        total_loads = 0
        cross_block = 0
        hot_sites = 0
        logical_destination_visits = 0
        for function in module.functions:
            if function.external:
                continue
            report = analyze_repeated_load_availability(
                SSABuilder.build_function(function)
            )
            total_loads += len(report.candidates)
            candidates = [
                candidate
                for candidate in report.candidates
                if candidate.cross_block_available
            ]
            if not candidates:
                continue
            function_candidates: list[dict[str, object]] = []
            function_hot = 0
            function_visits = 0
            for candidate in candidates:
                block_visits = visits.get((function.name, candidate.block), 0)
                function_hot += block_visits > 0
                function_visits += block_visits
                function_candidates.append(
                    {
                        "block": candidate.block,
                        "instruction_index": candidate.instruction_index,
                        "storage": {
                            "memory_object": candidate.storage.memory_object,
                            "index": candidate.storage.index,
                        },
                        "source_load_sites": [
                            {"block": block, "instruction_index": index}
                            for block, index in candidate.state.load_sites
                        ],
                        "logical_destination_block_visits": block_visits,
                    }
                )
            cross_block += len(candidates)
            hot_sites += function_hot
            logical_destination_visits += function_visits
            function_rows.append(
                {
                    "function": function.name,
                    "cross_block_candidate_count": len(candidates),
                    "hot_candidate_count": function_hot,
                    "logical_destination_block_visits": function_visits,
                    "candidates": function_candidates,
                }
            )
        workloads[workload_id] = {
            "source_path": manifest_row["s3_source"],
            "source_sha256": source_sha,
            "windows_checkout_source_sha256": _sha256(checkout_bytes),
            "dataset_sha256": workload["dataset_sha256"],
            "direct_load_sites_analyzed": total_loads,
            "cross_block_candidate_count": cross_block,
            "hot_candidate_count": hot_sites,
            "logical_destination_block_visits": logical_destination_visits,
            "functions": function_rows,
        }

    return {
        "schema_version": "1.0.0",
        "experiment_id": "EXP-S3-110-LOAD-001",
        "classification": "DIAGNOSTIC_CENSUS_NOT_NATIVE_OR_RUNTIME_EVIDENCE",
        "control": {
            "s3_commit": "e27dff1e712e50271df9f860669cd714e28f4ce7",
            "profile_path": str(profile_path.relative_to(ROOT)),
            "profile_sha256": _sha256(profile_bytes),
            "optimization": "O1",
        },
        "analysis": {
            "storage": "direct frame memory object plus proven constant-or-SSA index",
            "candidate_rule": "prior exact-cell LOAD is available on all reachable CFG paths; at least one source load is in a different block; loaded type agrees",
            "kills": "must-alias store; conservative unknown for may-alias store, call, indirect store, or unclassified effect",
            "same_block_candidates_reported": False,
            "hotness": "logical destination basic-block visits from the correctness-checked 1.9 profile; not hardware counts or candidate execution measurements",
            "transformation_applied": False,
            "runtime_measured": False,
        },
        "workloads": workloads,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = _run(args.profile.resolve())
    encoded = _canonical_json_bytes(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"OUTPUT={args.output}")
    print(f"OUTPUT_SHA256={_sha256(encoded)}")
    for workload_id, row in result["workloads"].items():
        print(
            f"{workload_id}: loads={row['direct_load_sites_analyzed']} "
            f"cross_block={row['cross_block_candidate_count']} "
            f"hot={row['hot_candidate_count']} "
            f"logical_destination_visits={row['logical_destination_block_visits']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
