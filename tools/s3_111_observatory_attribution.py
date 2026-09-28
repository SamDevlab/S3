"""Join native instruction lineage to the bounded logical block profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _rows(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{label} must be a list of objects")
    return value


def _memory_address_form(operands: str) -> str:
    match = re.search(r"\[([^\]]+)\]", operands)
    if not match:
        return "NO_BRACKETED_MEMORY_OPERAND"
    expression = match.group(1).replace(" ", "").lower()
    if expression.startswith("rip+") or expression == "rip":
        return "RIP_RELATIVE"
    has_index = bool(re.search(r"\*[1248](?:$|[+-])", expression)) or bool(
        re.search(r"\+[re]?(?:ax|bx|cx|dx|si|di|sp|bp|[0-9]+)(?:\]|$)", expression)
    )
    has_displacement = bool(re.search(r"(?:\+|-)0x[0-9a-f]+", expression))
    has_register = bool(re.search(r"\b(?:r(?:ax|bx|cx|dx|si|di|sp|bp|[0-9]+)|e(?:ax|bx|cx|dx|si|di|sp|bp))\b", expression))
    if has_index and "*" in expression:
        return "BASE_INDEX_SCALE"
    if has_index:
        return "BASE_INDEX"
    if has_register and has_displacement:
        return "BASE_DISPLACEMENT"
    if has_register:
        return "BASE_ONLY"
    return "ADDRESS_FORM_UNKNOWN"


def analyze(
    observatory_paths: list[Path],
    profile_path: Path,
    *,
    expected_commit: str,
    expected_tree: str,
) -> dict[str, Any]:
    profile_bytes = profile_path.read_bytes()
    profile = _object(json.loads(profile_bytes), "profile")
    profile_results = _object(profile.get("results"), "profile.results")
    results: list[dict[str, Any]] = []

    for path in observatory_paths:
        data = _object(json.loads(path.read_bytes()), str(path))
        provenance = _object(data.get("provenance"), f"{path}.provenance")
        if provenance.get("git_head") != expected_commit:
            raise ValueError(f"{path}: source commit does not match frozen control")
        if provenance.get("git_tree") != expected_tree:
            raise ValueError(f"{path}: source tree does not match frozen control")
        if provenance.get("git_worktree_dirty") is not False:
            raise ValueError(f"{path}: source worktree was not clean")

        source_sha = provenance.get("source_sha256")
        matching_workloads = [
            workload_id
            for workload_id, row in profile_results.items()
            if isinstance(row, dict) and row.get("source_sha256") == source_sha
        ]
        if len(matching_workloads) != 1:
            raise ValueError(
                f"{path}: source SHA must identify exactly one profile workload"
            )
        workload_id = matching_workloads[0]
        profile_result = _object(profile_results[workload_id], f"profile.{workload_id}")
        hot_blocks = _rows(profile_result.get("hot_blocks"), f"profile.{workload_id}.hot_blocks")
        visits: dict[tuple[str, str], int] = {}
        for row in hot_blocks:
            function, block, count = row.get("function"), row.get("block"), row.get("logical_block_executions")
            if not isinstance(function, str) or not isinstance(block, str):
                raise ValueError("profile block identity is invalid")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError("profile block visit count is invalid")
            key = (function, block)
            if key in visits:
                raise ValueError(f"duplicate profile block identity: {key}")
            visits[key] = count

        instructions = _rows(data.get("native_instructions"), f"{path}.native_instructions")
        machine_categories: Counter[str] = Counter()
        hot_subset_weights: Counter[str] = Counter()
        move_origin: Counter[str] = Counter()
        move_lineage: Counter[str] = Counter()
        hot_move_lineage_weight: Counter[str] = Counter()
        control_mnemonics: Counter[str] = Counter()
        control_origin: Counter[str] = Counter()
        hot_control_lineage_weight: Counter[str] = Counter()
        address_forms: Counter[str] = Counter()
        mapped_hot_instructions = 0
        for row in instructions:
            category = row.get("native_category")
            if not isinstance(category, str):
                raise ValueError("native instruction lacks a category")
            machine_categories[category] += 1
            function, block = row.get("function"), row.get("assembly_block")
            hot_visits = visits.get((function, block), 0) if isinstance(function, str) and isinstance(block, str) else 0
            if hot_visits:
                hot_subset_weights[category] += hot_visits
                mapped_hot_instructions += 1

            origins = row.get("assembly_opcodes")
            if not isinstance(origins, list) or any(not isinstance(op, str) for op in origins):
                origins = []
            lineage = (
                "UNMAPPED"
                if row.get("origin_status") != "MAPPED"
                else "MULTIPLE_SOURCE_OPCODES"
                if len(origins) > 1
                else origins[0]
                if origins
                else "MAPPED_WITHOUT_ASSEMBLY_OPCODE"
            )
            if category == "MOVE":
                move_origin[row.get("origin_category", "UNKNOWN")] += 1
                move_lineage[lineage] += 1
                if hot_visits:
                    hot_move_lineage_weight[lineage] += hot_visits
            mnemonic = row.get("mnemonic")
            if isinstance(mnemonic, str) and (
                mnemonic.lower().startswith("j")
                or mnemonic.lower() in {"call", "callq", "ret", "retq"}
            ):
                control_mnemonics[mnemonic.lower()] += 1
                control_origin[lineage] += 1
                if hot_visits:
                    hot_control_lineage_weight[lineage] += hot_visits
            if category == "MEMORY_ACCESS" and isinstance(row.get("operands"), str):
                address_forms[_memory_address_form(row["operands"])] += 1

        results.append(
            {
                "workload_id": workload_id,
                "source_sha256": provenance.get("source_sha256"),
                "observatory_sha256": _sha256(path),
                "logical_profile_sha256": _sha256(profile_path),
                "logical_hot_block_rows": len(visits),
                "native_instruction_rows": len(instructions),
                "native_machine_categories_static": dict(sorted(machine_categories.items())),
                "hot_block_subset_join": {
                    "scope": "displayed logical hot_blocks subset; not all blocks",
                    "mapped_native_instruction_rows": mapped_hot_instructions,
                    "visit_weight_by_native_category": dict(sorted(hot_subset_weights.items())),
                    "interpretation": "instruction-row count multiplied by block-entry visits; not retired instructions or runtime share",
                },
                "move_provenance": {
                    "static_count_by_origin_category": dict(sorted(move_origin.items())),
                    "static_count_by_assembly_opcode_lineage": dict(sorted(move_lineage.items())),
                    "hot_block_subset_lineage_visit_weight": dict(sorted(hot_move_lineage_weight.items())),
                    "limitation": "lineage identifies the associated Assembly opcode, not semantic reason or allocator cause",
                },
                "control_provenance": {
                    "static_count_by_mnemonic": dict(sorted(control_mnemonics.items())),
                    "static_count_by_assembly_opcode_lineage": dict(sorted(control_origin.items())),
                    "hot_block_subset_lineage_visit_weight": dict(sorted(hot_control_lineage_weight.items())),
                    "limitation": "mnemonic and origin do not prove taken-edge frequency or runtime cost",
                },
                "memory_address_forms_static": dict(sorted(address_forms.items())),
            }
        )

    return {
        "schema_version": "1.0.0",
        "experiment_id": "EXP-S3-111-MOVE-CTRL-ADDR-001",
        "classification": "STATIC_INSTRUCTION_LINEAGE_WITH_BOUNDED_LOGICAL_PROFILE_JOIN",
        "control": {
            "s3_commit": expected_commit,
            "s3_tree": expected_tree,
            "optimization": "O1",
            "profile_scope": "logical basic-block entries",
            "hardware_counters": "UNAVAILABLE_BY_POLICY",
        },
        "workloads": sorted(results, key=lambda row: row["workload_id"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observatory-dir", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(args.observatory_dir.glob("*-native-observatory-v1.json"))
    if len(paths) != 3:
        raise SystemExit(f"expected exactly 3 observatory JSON files, found {len(paths)}")
    result = analyze(paths, args.profile, expected_commit=args.source_sha, expected_tree=args.source_tree)
    encoded = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"OUTPUT={args.output}")
    print(f"OUTPUT_SHA256={hashlib.sha256(encoded).hexdigest()}")
    for row in result["workloads"]:
        print(f"{row['workload_id']}: moves={row['move_provenance']['static_count_by_origin_category']} address={row['memory_address_forms_static']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
