"""Project initialization-analysis state pressure without materializing dense reports.

This audit is architectural evidence only. It compiles the selected S3 source to
ordinary IR, counts memory cells and reachable CFG blocks, and compares the
legacy dense-map state shape with a two-bitset internal representation. It does
not run native qualification and does not mutate the canonical compiler source.
"""

from __future__ import annotations

import argparse
import json
from math import ceil
from pathlib import Path

from bootstrap.s3.ir import IRFunction, IROpcode
from bootstrap.s3.pipeline import compile_source


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "initialization-analysis-scalability-contract.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "initialization-analysis-scalability-audit.json"
)
WORD_BITS = 64


def _successors(function: IRFunction) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for block in function.blocks:
        if not block.instructions:
            result[block.name] = ()
            continue
        terminator = block.instructions[-1]
        if terminator.opcode in {IROpcode.JUMP, IROpcode.BRANCH3}:
            result[block.name] = terminator.targets
        else:
            result[block.name] = ()
    return result


def _reachable_block_names(function: IRFunction) -> tuple[str, ...]:
    successors = _successors(function)
    if not function.blocks:
        return ()
    entry = "entry" if "entry" in successors else function.blocks[0].name
    seen: set[str] = set()
    pending = [entry]
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        pending.extend(target for target in successors.get(name, ()) if target not in seen)
    return tuple(sorted(seen))


def project_state_shape(total_cells: int, reachable_blocks: int) -> dict[str, int | float]:
    if total_cells < 0 or reachable_blocks < 0:
        raise ValueError("cell/block counts must be non-negative")
    state_maps = 1 + 2 * reachable_blocks if total_cells else 0
    dense_entries = total_cells * state_maps
    detailed_report_entries = total_cells * 2 * reachable_blocks
    words_per_bitset = ceil(total_cells / WORD_BITS) if total_cells else 0
    two_bitset_words = words_per_bitset * 2 * state_maps
    logical_bits = total_cells * 2 * state_maps
    reduction = dense_entries / two_bitset_words if two_bitset_words else 0.0
    return {
        "state_maps_including_initial": state_maps,
        "legacy_dense_state_entries": dense_entries,
        "legacy_detailed_report_cell_entries": detailed_report_entries,
        "bitset_word_bits": WORD_BITS,
        "words_per_bitset": words_per_bitset,
        "two_bitset_words_for_same_state_count": two_bitset_words,
        "two_bitset_logical_bits": logical_bits,
        "dense_entries_per_bitset_word_projection": reduction,
    }


def _function_projection(function: IRFunction) -> dict[str, object]:
    reachable = _reachable_block_names(function)
    memory_lengths = [memory.length for memory in function.memory_objects]
    total_cells = sum(memory_lengths)
    projection = project_state_shape(total_cells, len(reachable))
    return {
        "name": function.name,
        "external": function.external,
        "memory_object_count": len(function.memory_objects),
        "memory_lengths": memory_lengths,
        "total_memory_cells": total_cells,
        "block_count": len(function.blocks),
        "reachable_block_count": len(reachable),
        "reachable_blocks": list(reachable),
        "projection": projection,
    }


def audit_source(source: str, contract: dict[str, object]) -> dict[str, object]:
    compilation = compile_source(source, optimization="O0")
    ir = compilation.ir
    if ir is None:
        raise ValueError("initialization scalability audit requires ordinary IR")
    functions = [
        _function_projection(function)
        for function in ir.functions
        if not function.external
    ]
    totals = {
        "functions": len(functions),
        "memory_objects": sum(int(item["memory_object_count"]) for item in functions),
        "memory_cells": sum(int(item["total_memory_cells"]) for item in functions),
        "reachable_blocks": sum(int(item["reachable_block_count"]) for item in functions),
        "legacy_dense_state_entries": sum(
            int(item["projection"]["legacy_dense_state_entries"])
            for item in functions
        ),
        "two_bitset_words": sum(
            int(item["projection"]["two_bitset_words_for_same_state_count"])
            for item in functions
        ),
    }
    hottest = max(
        functions,
        key=lambda item: int(item["projection"]["legacy_dense_state_entries"]),
        default=None,
    )
    contract_ok = (
        contract.get("schema")
        == "s3.selfhost.initialization-analysis-scalability-contract.v1"
        and isinstance(contract.get("semantic_invariants"), list)
        and isinstance(contract.get("report_policy"), dict)
    )
    return {
        "schema": "s3.selfhost.initialization-analysis-scalability-audit.v1",
        "status": "STATIC_STATE_SHAPE_MEASURED" if contract_ok else "FAIL_CONTRACT",
        "native_evidence": False,
        "runtime_rss_measurement": False,
        "canonical_source_mutated": False,
        "contract_valid": contract_ok,
        "functions": functions,
        "totals": totals,
        "hottest_function": hottest,
        "interpretation": {
            "legacy_projection": (
                "Logical dict-entry count implied by initial + entry/exit dense "
                "StateMap shapes. It is not a byte/RSS estimate."
            ),
            "bitset_projection": (
                "64-bit word count for two bitsets across the same number of "
                "logical states. Python/container overhead is intentionally excluded."
            ),
            "detailed_report": (
                "Validation-only callers can avoid the report cell tuples, but "
                "must still execute identical semantic validation."
            ),
        },
        "qualification": {
            "native_evidence": False,
            "stage1_source_change": False,
            "stage2_allowed": False,
            "full_self_hosting": False,
            "next": (
                "COMPARE_MAIN_AGENT_COMPACT_ANALYZER_AGAINST_SEMANTIC_CONTRACT"
                if contract_ok
                else "REPAIR_SCALABILITY_CONTRACT"
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    contract = json.loads(args.contract.resolve().read_text(encoding="utf-8"))
    if not isinstance(contract, dict):
        raise ValueError("scalability contract must be a JSON object")
    result = audit_source(
        args.source.resolve().read_text(encoding="utf-8"),
        contract,
    )
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"MEMORY_CELLS={result['totals']['memory_cells']}")
    print(
        "LEGACY_DENSE_STATE_ENTRIES="
        f"{result['totals']['legacy_dense_state_entries']}"
    )
    print(f"TWO_BITSET_WORDS={result['totals']['two_bitset_words']}")
    print("NATIVE_EVIDENCE=False")
    print(f"NEXT={result['qualification']['next']}")
    return 0 if result["status"] == "STATIC_STATE_SHAPE_MEASURED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
