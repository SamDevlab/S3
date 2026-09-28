"""Report the first existing loop-induction recognizer predicate per loop.

This diagnostic intentionally mirrors, but does not modify, the conservative
recognizers in ``ssa_optimizer.loops``. It establishes why current workload
loops remain unrecognized; it does not establish vector legality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.ir import IRFunction, IRInstruction, IROpcode
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa_optimizer import loops as loop_analysis

WORKLOADS = (
    ("energy", "benchmarks/workloads/real_world/energy_series_aggregation.s3", "energy_series_aggregation"),
    ("point-cloud", "benchmarks/workloads/real_world/point_cloud_summary.s3", "point_cloud_summary"),
    ("raster", "benchmarks/workloads/real_world/raster_window_statistics.s3", "raster_window_statistics"),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _definitions(function: IRFunction) -> dict[int, IRInstruction]:
    return {
        result: instruction
        for block in function.blocks
        for instruction in block.instructions
        for result in instruction.results
    }


def _condition_diagnostic(
    function: IRFunction, header: str, definitions: dict[int, IRInstruction]
) -> tuple[str, Any | None]:
    blocks = {block.name: block for block in function.blocks}
    block = blocks[header]
    if not block.instructions or block.instructions[-1].opcode is not IROpcode.BRANCH3:
        return "HEADER_NOT_TERMINATED_BY_BRANCH3", None
    branch = block.instructions[-1]
    if len(branch.operands) != 1 or len(branch.targets) != 3:
        return "HEADER_BRANCH3_SHAPE", None
    comparison = definitions.get(branch.operands[0])
    if comparison is None or comparison.opcode is not IROpcode.COMPARE or len(comparison.operands) != 2:
        return "HEADER_CONDITION_NOT_BINARY_COMPARE", None

    relation_arms = [blocks.get(name) for name in branch.targets]
    if any(arm is None or not arm.instructions for arm in relation_arms):
        return "RELATION_ARM_MISSING_OR_EMPTY", None
    joins: set[str] = set()
    condition_memory: int | None = None
    values: list[int | float | None] = []
    for arm in relation_arms:
        assert arm is not None
        terminator = arm.instructions[-1]
        stores = [item for item in arm.instructions if item.opcode is IROpcode.STORE]
        if terminator.opcode is not IROpcode.JUMP or len(terminator.targets) != 1:
            return "RELATION_ARM_NOT_SINGLE_TARGET_JUMP", None
        if len(stores) != 1:
            return "RELATION_ARM_STORE_COUNT", None
        if len(stores[0].operands) != 2 or stores[0].memory is None:
            return "RELATION_ARM_STORE_SHAPE_OR_MEMORY", None
        joins.add(terminator.targets[0])
        if condition_memory is None:
            condition_memory = stores[0].memory
        elif condition_memory != stores[0].memory:
            return "RELATION_ARMS_WRITE_DIFFERENT_MEMORY", None
        values.append(loop_analysis._constant_register(stores[0].operands[1], definitions))
    if len(joins) != 1:
        return "RELATION_ARMS_DO_NOT_SHARE_JOIN", None
    if condition_memory is None:
        return "RELATION_CONDITION_MEMORY_UNAVAILABLE", None
    if values != [-1, 0, 0]:
        return "RELATION_ARM_VALUES_NOT_LESS_THAN_ENCODING", None

    join = blocks.get(next(iter(joins)))
    if join is None or not join.instructions:
        return "RELATION_JOIN_MISSING_OR_EMPTY", None
    join_branch = join.instructions[-1]
    if join_branch.opcode is not IROpcode.BRANCH3 or len(join_branch.operands) != 1 or len(join_branch.targets) != 3:
        return "RELATION_JOIN_NOT_BRANCH3", None
    condition_load = definitions.get(join_branch.operands[0])
    if condition_load is None or condition_load.opcode is not IROpcode.LOAD:
        return "RELATION_JOIN_CONDITION_NOT_LOAD", None
    if condition_load.memory != condition_memory:
        return "RELATION_JOIN_LOAD_MEMORY_MISMATCH", None

    condition = loop_analysis._LoopCondition(
        body=join_branch.targets[0],
        join=join.name,
        condition_memory=condition_memory,
        relation_arms=tuple(branch.targets),
    )
    return "CONDITION_RECOGNIZED", condition


def first_induction_failure(
    function: IRFunction,
    loop: Any,
    condition: Any | None,
    condition_failure: str = "CONDITION_NOT_RECOGNIZED",
) -> str:
    """Return the first failing predicate in the current recognizer's order."""
    definitions = _definitions(function)
    blocks = {block.name: block for block in function.blocks}
    if condition is None:
        return condition_failure
    if condition.body not in loop.blocks:
        return "SELECTED_BODY_OUTSIDE_NATURAL_LOOP"
    if condition.join not in loop.blocks:
        return "CONDITION_JOIN_OUTSIDE_NATURAL_LOOP"
    if any(arm not in loop.blocks for arm in condition.relation_arms):
        return "RELATION_ARM_OUTSIDE_NATURAL_LOOP"

    if len(loop.backedges) != 1:
        return "BACKEDGE_COUNT_NOT_ONE"
    if loop.backedges[0] != condition.body:
        return "BACKEDGE_TAIL_DIFFERS_FROM_SELECTED_BODY"
    if len(loop.preheaders) != 1:
        return "PREHEADER_COUNT_NOT_ONE"
    if not loop.exits:
        return "LOOP_HAS_NO_EXIT"

    preheader_block = blocks[loop.preheaders[0]]
    body_block = blocks[condition.body]
    if not preheader_block.instructions:
        return "PREHEADER_EMPTY"
    if preheader_block.instructions[-1].opcode is not IROpcode.JUMP:
        return "PREHEADER_TERMINATOR_NOT_JUMP"
    if preheader_block.instructions[-1].targets != (loop.header,):
        return "PREHEADER_JUMP_NOT_DIRECT_TO_HEADER"
    if not body_block.instructions:
        return "SELECTED_BODY_EMPTY"
    if body_block.instructions[-1].opcode is not IROpcode.JUMP:
        return "SELECTED_BODY_TERMINATOR_NOT_JUMP"
    if body_block.instructions[-1].targets != (loop.header,):
        return "SELECTED_BODY_JUMP_NOT_DIRECT_TO_HEADER"
    if any(
        instruction.opcode in {IROpcode.JUMP, IROpcode.BRANCH3, IROpcode.RETURN}
        for instruction in body_block.instructions[:-1]
    ):
        return "SELECTED_BODY_HAS_INTERNAL_CONTROL_TERMINATOR"

    header_block = blocks[loop.header]
    if not header_block.instructions or header_block.instructions[-1].opcode is not IROpcode.BRANCH3:
        return "HEADER_NOT_TERMINATED_BY_BRANCH3"
    branch = header_block.instructions[-1]
    comparison = definitions.get(branch.operands[0]) if branch.operands else None
    if comparison is None or comparison.opcode is not IROpcode.COMPARE or len(comparison.operands) != 2:
        return "HEADER_CONDITION_NOT_BINARY_COMPARE"
    index_load = definitions.get(
        loop_analysis._copy_source(comparison.operands[0], definitions)
    )
    if index_load is None or index_load.opcode is not IROpcode.LOAD:
        return "COMPARE_LEFT_OPERAND_NOT_INDUCTION_LOAD"
    induction_memory = index_load.memory
    if induction_memory is None:
        return "INDUCTION_LOAD_WITHOUT_MEMORY_ID"
    if any(
        instruction.opcode is IROpcode.ADDRESS_OF and instruction.memory == induction_memory
        for block in function.blocks
        for instruction in block.instructions
    ):
        return "INDUCTION_MEMORY_ADDRESS_ESCAPES"

    preheader = loop.preheaders[0]
    initializers = [
        instruction for instruction in blocks[preheader].instructions
        if instruction.opcode is IROpcode.STORE and instruction.memory == induction_memory
    ]
    all_stores = [
        instruction for block in function.blocks for instruction in block.instructions
        if instruction.opcode is IROpcode.STORE and instruction.memory == induction_memory
    ]
    if len(initializers) != 1:
        return "INDUCTION_INITIALIZER_COUNT_NOT_ONE"
    if len(initializers[0].operands) != 2:
        return "INDUCTION_INITIALIZER_STORE_SHAPE"
    if len(all_stores) != 2:
        return "INDUCTION_STORE_COUNT_NOT_TWO"
    initial = loop_analysis._constant_register(initializers[0].operands[1], definitions)
    if isinstance(initial, bool) or not isinstance(initial, int):
        return "INDUCTION_INITIAL_VALUE_NOT_INTEGER_CONSTANT"
    if initial < 0:
        return "INDUCTION_INITIAL_VALUE_NEGATIVE"

    updates: list[tuple[int, IRInstruction, int]] = []
    for instruction_index, instruction in enumerate(body_block.instructions[:-1]):
        if instruction.opcode is not IROpcode.ADD or len(instruction.operands) != 2:
            continue
        for load_register, step_register in (
            (instruction.operands[0], instruction.operands[1]),
            (instruction.operands[1], instruction.operands[0]),
        ):
            load = definitions.get(loop_analysis._copy_source(load_register, definitions))
            step = loop_analysis._constant_register(step_register, definitions)
            if (
                load is not None and load.opcode is IROpcode.LOAD
                and load.memory == induction_memory and isinstance(step, int)
                and not isinstance(step, bool) and step > 0
            ):
                updates.append((instruction_index, instruction, step))
                break
    induction_stores = [
        (index, instruction) for index, instruction in enumerate(body_block.instructions)
        if instruction.opcode is IROpcode.STORE and instruction.memory == induction_memory
    ]
    if len(updates) != 1:
        return "POSITIVE_CONSTANT_INDUCTION_UPDATE_COUNT_NOT_ONE"
    if len(induction_stores) != 1:
        return "BODY_INDUCTION_STORE_COUNT_NOT_ONE"
    update_index, update, _step = updates[0]
    store_index, induction_store = induction_stores[0]
    if store_index <= update_index:
        return "INDUCTION_STORE_PRECEDES_UPDATE"
    if len(induction_store.operands) != 2:
        return "INDUCTION_UPDATE_STORE_SHAPE"
    if induction_store.operands[1] not in update.results:
        return "INDUCTION_STORE_NOT_FED_BY_UPDATE"
    return "INDUCTION_PREDICATES_PASSED"


def _induction_memory_census(
    function: IRFunction, loop: Any, definitions: dict[int, IRInstruction]
) -> dict[str, Any]:
    blocks = {block.name: block for block in function.blocks}
    header = blocks[loop.header]
    if not header.instructions or header.instructions[-1].opcode is not IROpcode.BRANCH3:
        return {"candidate_memory": None, "store_sites": [], "update_sites": []}
    branch = header.instructions[-1]
    comparison = definitions.get(branch.operands[0]) if branch.operands else None
    if comparison is None or comparison.opcode is not IROpcode.COMPARE or len(comparison.operands) != 2:
        return {"candidate_memory": None, "store_sites": [], "update_sites": []}
    load = definitions.get(loop_analysis._copy_source(comparison.operands[0], definitions))
    memory = load.memory if load is not None and load.opcode is IROpcode.LOAD else None
    if memory is None:
        return {"candidate_memory": None, "store_sites": [], "update_sites": []}

    stores: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []
    for block in function.blocks:
        for index, instruction in enumerate(block.instructions):
            if instruction.opcode is IROpcode.STORE and instruction.memory == memory:
                stores.append({
                    "block": block.name,
                    "instruction_index": index,
                    "inside_natural_loop": block.name in loop.blocks,
                    "in_preheader": block.name in loop.preheaders,
                })
            if instruction.opcode is not IROpcode.ADD or len(instruction.operands) != 2:
                continue
            for load_register, step_register in (
                (instruction.operands[0], instruction.operands[1]),
                (instruction.operands[1], instruction.operands[0]),
            ):
                source_load = definitions.get(loop_analysis._copy_source(load_register, definitions))
                step = loop_analysis._constant_register(step_register, definitions)
                if (
                    source_load is not None and source_load.opcode is IROpcode.LOAD
                    and source_load.memory == memory and isinstance(step, int)
                    and not isinstance(step, bool) and step > 0
                ):
                    updates.append({
                        "block": block.name,
                        "instruction_index": index,
                        "step": step,
                        "inside_natural_loop": block.name in loop.blocks,
                    })
                    break
    return {
        "candidate_memory": memory,
        "store_sites": stores,
        "store_count_function_wide": len(stores),
        "store_count_in_loop": sum(item["inside_natural_loop"] for item in stores),
        "store_count_in_preheader": sum(item["in_preheader"] for item in stores),
        "update_sites": updates,
        "positive_constant_update_count_in_loop": sum(item["inside_natural_loop"] for item in updates),
        "scope_note": "Census only; block membership does not prove path coverage, dominance, alias safety, or one update per iteration.",
    }


def analyze_workloads() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for workload, source_relative, function_name in WORKLOADS:
        source_path = ROOT / source_relative
        source_bytes = source_path.read_bytes()
        compilation = compile_source(source_bytes.decode("utf-8"), OptimizationLevel.O1)
        ir, _assembly = compilation.require_ordinary_artifacts()
        functions = [
            function for function in ir.functions
            if function.name == function_name or function.name.endswith(f"__{function_name}")
        ]
        if len(functions) != 1:
            raise RuntimeError(f"expected one {function_name} function, found {len(functions)}")
        function = functions[0]
        definitions = _definitions(function)
        vector_report = loop_analysis.analyze_loop_facts(function)
        for loop in loop_analysis.discover_loop_info(function):
            condition_status, condition = _condition_diagnostic(function, loop.header, definitions)
            if condition is not None and (
                condition.body not in loop.blocks
                or condition.join not in loop.blocks
                or any(arm not in loop.blocks for arm in condition.relation_arms)
            ):
                condition_status = "CONDITION_COMPONENT_OUTSIDE_NATURAL_LOOP"
                condition = None
            first_failure = first_induction_failure(
                function, loop, condition, condition_failure=condition_status
            )
            recognized = (
                condition is not None
                and loop_analysis._recognize_induction(
                    function, loop, condition.body, definitions,
                    {block.name: block for block in function.blocks},
                ) is not None
            )
            rows.append({
                "workload": workload,
                "source_path": source_relative,
                "source_sha256": _sha(source_bytes),
                "function": function.name,
                "loop_header": loop.header,
                "natural_loop_blocks": len(loop.blocks),
                "backedges": list(loop.backedges),
                "preheaders": list(loop.preheaders),
                "exits": list(loop.exits),
                "condition_recognizer": condition_status,
                "selected_body": condition.body if condition is not None else None,
                "first_induction_predicate_failure": first_failure,
                "induction_memory_census": _induction_memory_census(function, loop, definitions),
                "induction_recognized_by_analyzer": recognized,
                "vector_bounds_proofs_for_function": len(vector_report.proofs),
                "interpretation": "Diagnostic of current static recognizer only; no legality, dependence, profitability, or SIMD claim.",
            })
    return {
        "schema": "s3-1.11-loop-predicate-diagnostics-v1",
        "source_revision": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip(),
        "source_tree": subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip(),
        "optimization": "O1",
        "python": platform.python_version(),
        "loops": rows,
        "summary": {
            "loops": len(rows),
            "condition_recognized": sum(row["condition_recognizer"] == "CONDITION_RECOGNIZED" for row in rows),
            "induction_predicates_passed": sum(row["first_induction_predicate_failure"] == "INDUCTION_PREDICATES_PASSED" for row in rows),
            "unknown_vector_legality_retained": len(rows),
            "simd_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze_workloads()
    encoded = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
