"""Test a profile-selected hot unconditional edge as native fallthrough."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.assembly import AssemblyFunction, AssemblyOpcode
from bootstrap.s3.backends.x86_64 import InstructionBudgetMode, NativeToolchain
from bootstrap.s3.backends.x86_64.emitter import (
    X8664Emitter,
    function_symbol,
    mangle_block,
)
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from tools import s3_15_native_workload_benchmark as benchmark

MAX_FRAMES = 1024
MAX_INSTRUCTIONS = 1_000_000_000


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_source(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _successors(block: object) -> tuple[str, ...]:
    instruction = block.instructions[-1]
    if instruction.opcode is AssemblyOpcode.TRET:
        return ()
    if instruction.opcode is AssemblyOpcode.TJMP and len(instruction.labels) == 1:
        return instruction.labels
    if instruction.opcode is AssemblyOpcode.TBR3 and len(instruction.labels) == 3:
        return instruction.labels
    raise ValueError(f"unsupported terminator in {block.label}: {instruction.opcode.value}")


def _dominators(function: AssemblyFunction) -> dict[str, set[str]]:
    if not function.blocks:
        return {}
    labels = [block.label for block in function.blocks]
    if len(labels) != len(set(labels)):
        raise ValueError(f"{function.name}: duplicate basic-block labels")
    label_set = set(labels)
    successors = {block.label: _successors(block) for block in function.blocks}
    predecessors = {label: set() for label in labels}
    for source, targets in successors.items():
        for target in targets:
            if target not in label_set:
                raise ValueError(f"{function.name}::{source}: missing target {target}")
            predecessors[target].add(source)

    entry = labels[0]
    reachable = {entry}
    pending = [entry]
    while pending:
        source = pending.pop()
        for target in successors[source]:
            if target not in reachable:
                reachable.add(target)
                pending.append(target)

    dominators = {
        label: ({entry} if label == entry else set(reachable))
        for label in reachable
    }
    changed = True
    while changed:
        changed = False
        for label in labels:
            if label == entry or label not in reachable:
                continue
            incoming = predecessors[label] & reachable
            common = set.intersection(*(dominators[item] for item in incoming)) if incoming else set()
            updated = {label} | common
            if updated != dominators[label]:
                dominators[label] = updated
                changed = True
    return dominators


def _candidate_edges(
    workload_id: str,
    program: object,
    hot_visits: dict[tuple[str, str], int],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for function in program.functions:
        if function.external or not function.blocks:
            continue
        positions = {block.label: index for index, block in enumerate(function.blocks)}
        dominators = _dominators(function)
        for block in function.blocks:
            terminator = block.instructions[-1]
            if terminator.opcode is not AssemblyOpcode.TJMP:
                continue
            target = terminator.labels[0]
            executions = hot_visits.get((function.name, block.label))
            if executions is None or executions <= 0 or target not in dominators.get(block.label, set()):
                continue
            if positions[target] == positions[block.label] + 1:
                continue
            if positions[target] == positions[block.label] + 1:
                continue
            result.append(
                {
                    "workload_id": workload_id,
                    "function": function.name,
                    "source_block": block.label,
                    "target_block": target,
                    "block_executions": executions,
                    "source_block_index": positions[block.label],
                    "target_block_index": positions[target],
                    "eligibility": "PROFILED_TJMP_TO_DOMINATING_LOOP_HEADER",
                }
            )
    return result


def reorder_and_remove_fallthrough_jump(
    assembly: str,
    *,
    function_name: str,
    block_labels: list[str],
    source_block: str,
    target_block: str,
) -> str:
    if len(block_labels) != len(set(block_labels)):
        raise ValueError("block labels must be unique")
    if source_block not in block_labels or target_block not in block_labels or source_block == target_block:
        raise ValueError("source and target must be distinct blocks in the function")

    order = list(block_labels)
    order.remove(target_block)
    order.insert(order.index(source_block) + 1, target_block)
    native_labels = {label: mangle_block(function_name, label) for label in block_labels}
    lines = assembly.splitlines()
    starts: dict[str, int] = {}
    for block, native in native_labels.items():
        matches = [index for index, line in enumerate(lines) if line.strip() == f"{native}:"]
        if len(matches) != 1:
            raise ValueError(f"expected one emitted label for {block}, found {len(matches)}")
        starts[block] = matches[0]
    size_marker = f".size {function_name}, .-{function_name}"
    size_matches = [index for index, line in enumerate(lines) if line.strip() == size_marker]
    if len(size_matches) != 1:
        raise ValueError(f"expected one function size marker for {function_name}")
    ordered_original = sorted(block_labels, key=starts.__getitem__)
    first = starts[ordered_original[0]]
    size_index = size_matches[0]
    if size_index <= starts[ordered_original[-1]]:
        raise ValueError("function size marker precedes a basic block")

    chunks: dict[str, list[str]] = {}
    for index, block in enumerate(ordered_original):
        end = starts[ordered_original[index + 1]] if index + 1 < len(ordered_original) else size_index
        chunks[block] = lines[starts[block]:end]

    reordered = lines[:first] + [line for block in order for line in chunks[block]] + lines[size_index:]
    source_chunk = chunks[source_block]
    source_last = next(
        (line.strip() for line in reversed(source_chunk) if line.strip()), None
    )
    expected_jump = f"jmp {native_labels[target_block]}"
    if source_last != expected_jump:
        raise ValueError(f"source block does not end in the expected jump: {source_last!r}")

    source_native = native_labels[source_block]
    source_line = next(i for i, line in enumerate(reordered) if line.strip() == f"{source_native}:")
    target_native = native_labels[target_block]
    target_line = next(
        i for i, line in enumerate(reordered)
        if i > source_line and line.strip() == f"{target_native}:"
    )
    intervening = [
        (i, line.strip())
        for i, line in enumerate(reordered[source_line + 1:target_line], start=source_line + 1)
        if line.strip()
    ]
    if not intervening or intervening[-1][1] != expected_jump:
        raise ValueError("source block does not end in the expected adjacent jump")
    jump_index = intervening[-1][0]
    following = next(
        (line.strip() for line in reordered[jump_index + 1:] if line.strip()), None
    )
    if following != f"{target_native}:":
        raise ValueError("jump target is not the next emitted block")
    reordered.pop(jump_index)
    if next(line.strip() for line in reordered[jump_index:] if line.strip()) != f"{target_native}:":
        raise ValueError("fallthrough target did not follow the removed jump")
    return "\n".join(reordered) + "\n"


def _native_metrics(path: Path, symbol: str) -> dict[str, int]:
    return benchmark._binary_metrics(path, symbol)


def _run_output(path: Path, workload: dict[str, Any], workload_id: str) -> tuple[int, list[float], str]:
    library = ctypes.CDLL(str(path))
    output = (ctypes.c_double * len(benchmark.OUTPUT_KEYS[workload_id]))()
    status = benchmark._make_call(library, workload, output)()
    values = list(output)
    benchmark._check_output(values, workload["expected_output"], workload_id)
    digest = _sha256(benchmark._json_bytes([round(value, 10) for value in values]))
    return status, values, digest


def run_experiment(
    *,
    source_root: Path,
    logical_profile_path: Path,
    edge_profile_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("hot fallthrough native experiment requires Linux x86-64")
    source_root = source_root.resolve()
    manifest, references = benchmark._load_inputs()
    references_by_id = {row["workload_id"]: row for row in references["workloads"]}
    logical_profile_bytes = logical_profile_path.read_bytes()
    logical_profile = json.loads(logical_profile_bytes)
    edge_profile_bytes = edge_profile_path.read_bytes()
    edge_profile = json.loads(edge_profile_bytes)
    source_commit = _git(source_root, "rev-parse", "HEAD")
    source_tree = _git(source_root, "rev-parse", "HEAD^{tree}")
    logical_provenance = logical_profile.get("source_provenance", {})
    edge_control = edge_profile.get("control", {})
    if (logical_provenance.get("git_head"), logical_provenance.get("git_tree"), logical_provenance.get("worktree_dirty")) != (source_commit, source_tree, False):
        raise ValueError("logical profile does not match the clean source control")
    if (edge_control.get("s3_commit"), edge_control.get("s3_tree")) != (source_commit, source_tree):
        raise ValueError("edge analysis does not match the current source control")
    if edge_control.get("source_profile_sha256") != _sha256(logical_profile_bytes):
        raise ValueError("edge analysis was not derived from these exact profile bytes")
    if edge_profile.get("experiment_id") != "EXP-S3-111-EDGE-PROFILE-002":
        raise ValueError("unsupported edge-profile experiment identity")

    all_candidates: list[dict[str, Any]] = []
    compiled_by_workload: dict[str, tuple[str, object, object]] = {}
    for workload_id, row in sorted(logical_profile["results"].items()):
        hot_visits = {
            (entry["function"], entry["block"]): entry["logical_block_executions"]
            for entry in row["hot_blocks"]
        }
        source_bytes = _canonical_source((source_root / row["source_path"]).read_bytes())
        source_sha = _sha256(source_bytes)
        if source_sha != row["source_sha256"]:
            raise ValueError(f"{workload_id}: logical profile source digest mismatch")
        compiled = compile_source(source_bytes.decode("utf-8"), optimization=OptimizationLevel.O1)
        _, program = compiled.require_ordinary_artifacts()
        compiled_by_workload[workload_id] = (source_sha, source_bytes, program)
        all_candidates.extend(_candidate_edges(workload_id, program, hot_visits))
    if not all_candidates:
        raise ValueError("no profiled non-adjacent single-successor loop backedge found")
    selected = sorted(
        all_candidates,
        key=lambda row: (-row["block_executions"], row["workload_id"], row["function"], row["source_block"]),
    )[0]
    reported_candidates = {
        (
            row.get("workload_id"), edge.get("function"), edge.get("source_block"),
            edge.get("target_block"), edge.get("edge_executions"),
        )
        for row in edge_profile.get("workloads", [])
        if isinstance(row, dict)
        for edge in row.get("fallthrough_candidates", [])
        if isinstance(edge, dict)
    }
    selected_identity = (
        selected["workload_id"], selected["function"], selected["source_block"],
        selected["target_block"], selected["block_executions"],
    )
    if selected_identity not in reported_candidates:
        raise ValueError("selected backedge is not in the exact edge-analysis candidate set")
    selected["edge_executions"] = selected["block_executions"]
    selected["edge_count_basis"] = "source block is a single-successor TJMP; its recorded entry count equals this edge count"
    workload_id = selected["workload_id"]
    source_sha, source_bytes, program = compiled_by_workload[workload_id]
    function = next(function for function in program.functions if function.name == selected["function"])
    terminator = next(
        block.instructions[-1]
        for block in function.blocks
        if block.label == selected["source_block"]
    )
    if terminator.opcode is not AssemblyOpcode.TJMP or terminator.labels != (selected["target_block"],):
        raise ValueError("selected profile edge no longer matches the pinned Assembly terminator")

    ordinary_assembly = X8664Emitter(
        program,
        max_frames=MAX_FRAMES,
        max_instructions=MAX_INSTRUCTIONS,
        register_allocation=True,
        instruction_budget_mode=InstructionBudgetMode.PER_INSTRUCTION,
    ).emit()
    candidate_assembly = reorder_and_remove_fallthrough_jump(
        ordinary_assembly,
        function_name=function.name,
        block_labels=[block.label for block in function.blocks],
        source_block=selected["source_block"],
        target_block=selected["target_block"],
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = output_dir / f"{workload_id}.baseline.so"
    candidate_path = output_dir / f"{workload_id}.hot-fallthrough.so"
    toolchain = NativeToolchain.detect()
    toolchain.build_shared(ordinary_assembly, baseline_path)
    toolchain.build_shared(candidate_assembly, candidate_path)

    workload = references_by_id[workload_id]
    baseline_status, baseline_values, baseline_output_sha = _run_output(baseline_path, workload, workload_id)
    candidate_status, candidate_values, candidate_output_sha = _run_output(candidate_path, workload, workload_id)
    if baseline_status != candidate_status or baseline_status != 0:
        raise RuntimeError("baseline and candidate native status differ or fail")
    if baseline_values != candidate_values or baseline_output_sha != candidate_output_sha:
        raise RuntimeError("hot-fallthrough native output differs from the baseline")

    baseline_metrics = _native_metrics(baseline_path, function_symbol(function))
    candidate_metrics = _native_metrics(candidate_path, function_symbol(function))
    delta = {key: candidate_metrics[key] - baseline_metrics[key] for key in baseline_metrics}
    return {
        "schema_version": "1.0.0",
        "experiment_id": "EXP-S3-111-HOT-FALLTHROUGH-001",
        "status": "PASS_NATIVE_CORRECTNESS",
        "classification": "PROFILE_SELECTED_SINGLE_BACKEDGE_LAYOUT_PROTOTYPE",
        "control": {
            "s3_commit": source_commit,
            "s3_tree": source_tree,
            "compiler_source_dirty": bool(_git(source_root, "status", "--porcelain", "--", "bootstrap/s3")),
            "logical_profile_sha256": _sha256(logical_profile_bytes),
            "edge_analysis_sha256": _sha256(edge_profile_bytes),
            "analysis_tool_sha256": _sha256(Path(__file__).read_bytes()),
            "target": "Linux x86-64",
            "optimization": "O1",
            "instruction_budget_mode": "per-instruction",
            "register_allocation": True,
            "transform_scope": "reorder emitted native basic-block text and remove one proven adjacent unconditional jump; no Assembly IR, compiler source, allocator, or semantics change",
            "timing_performed": False,
            "pmu_used": False,
        },
        "candidate": selected,
        "workload": {
            "workload_id": workload_id,
            "source_path": logical_profile["results"][workload_id]["source_path"],
            "source_sha256_canonical_lf": source_sha,
            "source_bytes_canonical_lf": len(source_bytes),
            "native_status": baseline_status,
            "baseline_output_sha256": baseline_output_sha,
            "candidate_output_sha256": candidate_output_sha,
            "baseline_candidate_values_equal": True,
            "reference_correctness": "PASS_BASELINE_AND_CANDIDATE",
        },
        "artifacts": {
            "baseline": {"file_name": baseline_path.name, "bytes": baseline_path.stat().st_size, "sha256": _sha256(baseline_path.read_bytes())},
            "candidate": {"file_name": candidate_path.name, "bytes": candidate_path.stat().st_size, "sha256": _sha256(candidate_path.read_bytes())},
            "baseline_assembly_sha256": _sha256(ordinary_assembly.encode()),
            "candidate_assembly_sha256": _sha256(candidate_assembly.encode()),
        },
        "native_structure": {
            "baseline": baseline_metrics,
            "candidate": candidate_metrics,
            "candidate_minus_baseline": delta,
        },
        "timing_class": "NOT_MEASURED",
        "native_speedup_claim": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--logical-profile", type=Path, required=True)
    parser.add_argument("--edge-profile", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    if (_git(source_root, "rev-parse", "HEAD"), _git(source_root, "rev-parse", "HEAD^{tree}")) != (args.source_sha, args.source_tree):
        raise SystemExit("S3 source checkout does not match the pinned control")
    if _git(source_root, "status", "--porcelain", "--", "bootstrap/s3"):
        raise SystemExit("compiler source differs from the pinned control")
    result = run_experiment(
        source_root=source_root,
        logical_profile_path=args.logical_profile,
        edge_profile_path=args.edge_profile,
        output_dir=args.output_dir,
    )
    encoded = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"OUTPUT={args.output}")
    print(f"OUTPUT_SHA256={_sha256(encoded)}")
    print(f"SELECTED_EDGE={result['candidate']['function']}::{result['candidate']['source_block']}->{result['candidate']['target_block']} executions={result['candidate']['block_executions']}")
    print(f"NATIVE_CORRECTNESS={result['status']}")
    print(f"BRANCH_DELTA={result['native_structure']['candidate_minus_baseline']['static_branches']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
