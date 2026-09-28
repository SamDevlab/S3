"""Infer exact single-successor edge counts from the pinned logical profile.

This analysis deliberately does not infer outcomes for conditional edges.
The source profile records block entries, not branch destinations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.assembly import AssemblyFunction, AssemblyOpcode
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_source_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _successors(block: object) -> tuple[str, ...]:
    instructions = getattr(block, "instructions", None)
    if not isinstance(instructions, (list, tuple)) or not instructions:
        raise ValueError("basic block must contain a terminator")
    terminator = instructions[-1]
    opcode = getattr(terminator, "opcode", None)
    labels = getattr(terminator, "labels", None)
    if opcode is AssemblyOpcode.TRET:
        if labels:
            raise ValueError("TRET cannot carry successor labels")
        return ()
    if opcode is AssemblyOpcode.TJMP:
        if not isinstance(labels, tuple) or len(labels) != 1:
            raise ValueError("TJMP must carry exactly one successor")
        return labels
    if opcode is AssemblyOpcode.TBR3:
        if not isinstance(labels, tuple) or len(labels) != 3:
            raise ValueError("TBR3 must carry exactly three successors")
        return labels
    raise ValueError(f"unsupported or missing block terminator: {opcode!r}")


def analyze_function(
    function: AssemblyFunction,
    visits: dict[tuple[str, str], int],
) -> dict[str, Any]:
    blocks = function.blocks
    labels = [block.label for block in blocks]
    if len(labels) != len(set(labels)):
        raise ValueError(f"{function.name}: duplicate basic-block label")
    positions = {label: index for index, label in enumerate(labels)}
    rows: list[dict[str, Any]] = []
    for index, block in enumerate(blocks):
        source_key = (function.name, block.label)
        source_visits = visits.get(source_key)
        successors = _successors(block)
        for target in successors:
            if target not in positions:
                raise ValueError(f"{function.name}::{block.label}: missing target {target}")

        if not successors:
            continue
        exact_single_successor = len(successors) == 1 and source_visits is not None
        for target in successors:
            target_index = positions[target]
            exact = exact_single_successor
            rows.append(
                {
                    "function": function.name,
                    "source_block": block.label,
                    "target_block": target,
                    "terminator": block.instructions[-1].opcode.value,
                    "source_block_index": index,
                    "target_block_index": target_index,
                    "currently_adjacent": target_index == index + 1,
                    "source_block_executions": source_visits,
                    "edge_executions": source_visits if exact else None,
                    "count_status": (
                        "EXACT_SINGLE_SUCCESSOR"
                        if exact
                        else "CONDITIONAL_EDGE_COUNT_UNOBSERVED"
                        if len(successors) > 1 and source_visits is not None
                        else "SOURCE_BLOCK_COUNT_NOT_REPORTED"
                    ),
                    "fallthrough_candidate_eligibility": bool(
                        exact and source_visits and target_index != index + 1
                    ),
                }
            )
    return {"function": function.name, "block_count": len(blocks), "edges": rows}


def analyze_profile(
    profile: dict[str, Any],
    source_root: Path,
    *,
    expected_commit: str,
    expected_tree: str,
    profile_sha256: str,
) -> dict[str, Any]:
    provenance = profile.get("source_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("profile lacks source_provenance")
    if provenance.get("git_head") != expected_commit or provenance.get("git_tree") != expected_tree:
        raise ValueError("profile source identity differs from the requested control")
    if provenance.get("worktree_dirty") is not False:
        raise ValueError("profile was not generated from a clean source worktree")
    results = profile.get("results")
    if not isinstance(results, dict) or not results:
        raise ValueError("profile.results must be a non-empty object")

    workloads: list[dict[str, Any]] = []
    for workload_id, profile_row in sorted(results.items()):
        if not isinstance(profile_row, dict):
            raise ValueError(f"{workload_id}: profile result must be an object")
        if profile_row.get("correctness") != "PASS_BASELINE_AND_INSTRUMENTED_OUTPUTS_MATCH_REFERENCE_AND_EACH_OTHER":
            raise ValueError(f"{workload_id}: source profile correctness did not pass")
        source_path = profile_row.get("source_path")
        source_sha = profile_row.get("source_sha256")
        hot_blocks = profile_row.get("hot_blocks")
        if not isinstance(source_path, str) or not isinstance(source_sha, str):
            raise ValueError(f"{workload_id}: source identity is malformed")
        if not isinstance(hot_blocks, list):
            raise ValueError(f"{workload_id}: hot_blocks must be a list")
        raw_source = (source_root / source_path).read_bytes()
        source = _canonical_source_bytes(raw_source)
        actual_source_sha = _sha256(source)
        if actual_source_sha != source_sha:
            raise ValueError(f"{workload_id}: source SHA mismatch")
        compiled = compile_source(source.decode("utf-8"), optimization=OptimizationLevel.O1)
        _, program = compiled.require_ordinary_artifacts()
        visits: dict[tuple[str, str], int] = {}
        for row in hot_blocks:
            if not isinstance(row, dict):
                raise ValueError(f"{workload_id}: malformed hot block row")
            function, block, count = row.get("function"), row.get("block"), row.get("logical_block_executions")
            if not isinstance(function, str) or not isinstance(block, str):
                raise ValueError(f"{workload_id}: invalid hot block identity")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError(f"{workload_id}: invalid block execution count")
            key = (function, block)
            if key in visits:
                raise ValueError(f"{workload_id}: duplicate hot block {key}")
            visits[key] = count

        functions = [function for function in program.functions if not function.external]
        function_rows = [analyze_function(function, visits) for function in functions]
        edges = [edge for row in function_rows for edge in row["edges"]]
        exact_edges = [edge for edge in edges if edge["edge_executions"] is not None]
        conditional_edges = [edge for edge in edges if edge["count_status"] == "CONDITIONAL_EDGE_COUNT_UNOBSERVED"]
        candidates = [
            edge for edge in exact_edges if edge["fallthrough_candidate_eligibility"]
        ]
        workloads.append(
            {
                "workload_id": workload_id,
                "source_path": source_path,
                "source_sha256": source_sha,
                "logical_profile_correctness": profile_row["correctness"],
                "reported_hot_block_rows": len(visits),
                "total_compiled_blocks": sum(row["block_count"] for row in function_rows),
                "exact_single_successor_edges": len(exact_edges),
                "conditional_edges_with_unknown_destination_counts": len(conditional_edges),
                "fallthrough_candidates": candidates,
                "candidate_count_status": "ELIGIBILITY_ONLY_NO_REORDER_NO_BRANCH_REMOVAL_NO_TIMING",
                "functions": function_rows,
            }
        )

    return {
        "schema_version": "1.0.0",
        "experiment_id": "EXP-S3-111-EDGE-PROFILE-002",
        "classification": "EXACT_COUNTS_FOR_REPORTED_SINGLE_SUCCESSOR_BLOCKS_ONLY",
        "control": {
            "s3_commit": expected_commit,
            "s3_tree": expected_tree,
            "optimization": "O1",
            "source_profile_sha256": profile_sha256,
            "profile_scope": "top 20 logical block rows by estimated structural weight per workload",
            "analysis_tool_sha256": _sha256(Path(__file__).read_bytes()),
            "conditional_edge_counts": "UNKNOWN_NOT_INFERRED_FROM_DESTINATION_BLOCK_COUNTS",
            "timing_performed": False,
            "native_build_performed": False,
            "pmu_used": False,
        },
        "workloads": workloads,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    current_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=args.source_root, check=True, capture_output=True, text=True).stdout.strip()
    current_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=args.source_root, check=True, capture_output=True, text=True).stdout.strip()
    changed_compiler = subprocess.run(["git", "status", "--porcelain", "--", "bootstrap/s3"], cwd=args.source_root, check=True, capture_output=True, text=True).stdout.strip()
    if (current_head, current_tree) != (args.source_sha, args.source_tree) or changed_compiler:
        raise SystemExit("source checkout does not match the clean pinned compiler control")
    profile_bytes = args.profile.read_bytes()
    profile = json.loads(profile_bytes)
    result = analyze_profile(
        profile,
        args.source_root,
        expected_commit=args.source_sha,
        expected_tree=args.source_tree,
        profile_sha256=_sha256(profile_bytes),
    )
    encoded = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"OUTPUT={args.output}")
    print(f"OUTPUT_SHA256={_sha256(encoded)}")
    for row in result["workloads"]:
        print(f"{row['workload_id']}: exact_edges={row['exact_single_successor_edges']} conditional_unknown={row['conditional_edges_with_unknown_destination_counts']} fallthrough_candidates={len(row['fallthrough_candidates'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
