"""Bounded analysis-only recurrence census across loop continuation CFGs."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.ir import IRFunction, IRInstruction, IROpcode
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa_optimizer import loops as loop_analysis
from tools.s3_111_loop_predicate_diagnostics import (
    WORKLOADS,
    _condition_diagnostic,
    _definitions,
    _induction_memory_census,
)


def _positive_recurrence_step(
    instruction: IRInstruction, memory: int, definitions: dict[int, IRInstruction]
) -> int | None:
    if instruction.opcode is not IROpcode.STORE or len(instruction.operands) != 2:
        return None
    stored = definitions.get(loop_analysis._copy_source(instruction.operands[1], definitions))
    if stored is None or stored.opcode is not IROpcode.ADD or len(stored.operands) != 2:
        return None
    for value_register, step_register in (
        (stored.operands[0], stored.operands[1]),
        (stored.operands[1], stored.operands[0]),
    ):
        value = definitions.get(loop_analysis._copy_source(value_register, definitions))
        step = loop_analysis._constant_register(step_register, definitions)
        if (
            value is not None and value.opcode is IROpcode.LOAD
            and value.memory == memory and isinstance(step, int)
            and not isinstance(step, bool) and step > 0
        ):
            return step
    return None


def probe_loop_recurrence(function: IRFunction, loop: Any) -> dict[str, Any]:
    definitions = _definitions(function)
    blocks = {block.name: block for block in function.blocks}
    condition_status, condition = _condition_diagnostic(function, loop.header, definitions)
    if condition is not None and (
        condition.body not in loop.blocks
        or condition.join not in loop.blocks
        or any(arm not in loop.blocks for arm in condition.relation_arms)
    ):
        condition_status = "CONDITION_COMPONENT_OUTSIDE_NATURAL_LOOP"
        condition = None
    if condition is None:
        return {
            "condition_recognizer": condition_status,
            "continuation_path_probe": "NOT_RUN_NO_CONDITION_BODY",
            "exactly_one_update_on_every_backedge": False,
        }

    census = _induction_memory_census(function, loop, definitions)
    memory = census["candidate_memory"]
    if memory is None:
        return {
            "condition_recognizer": condition_status,
            "continuation_path_probe": "NOT_RUN_NO_INDUCTION_MEMORY",
            "exactly_one_update_on_every_backedge": False,
        }

    events: dict[str, dict[int, bool]] = {}
    for block in function.blocks:
        by_index: dict[int, bool] = {}
        for index, instruction in enumerate(block.instructions):
            if instruction.opcode is IROpcode.STORE and instruction.memory == memory:
                by_index[index] = _positive_recurrence_step(instruction, memory, definitions) is not None
        if by_index:
            events[block.name] = by_index

    # Abstract path reachability tracks update counts saturated at 2 and whether
    # any non-recurrence store reaches the candidate induction cell.
    pending = deque([(condition.body, 0, False)])
    visited: set[tuple[str, int, bool]] = set()
    backedges: set[tuple[str, int, bool]] = set()
    exits: set[tuple[str, int, bool]] = set()
    returns: set[tuple[str, int, bool]] = set()
    opaque_terminators: set[tuple[str, str, int, bool]] = set()
    while pending:
        name, count, has_other_store = pending.popleft()
        state = (name, count, has_other_store)
        if state in visited:
            continue
        visited.add(state)
        block = blocks[name]
        for index, is_recurrence in sorted(events.get(name, {}).items()):
            if index >= len(block.instructions):
                continue
            if is_recurrence:
                count = min(2, count + 1)
            else:
                has_other_store = True
        if not block.instructions:
            opaque_terminators.add((name, "EMPTY_BLOCK", count, has_other_store))
            continue
        terminator = block.instructions[-1]
        if terminator.opcode is IROpcode.RETURN:
            returns.add((name, count, has_other_store))
            continue
        if terminator.opcode not in {IROpcode.JUMP, IROpcode.BRANCH3} or not terminator.targets:
            opaque_terminators.add((name, terminator.opcode.value, count, has_other_store))
            continue
        for target in terminator.targets:
            if target == loop.header:
                backedges.add((name, count, has_other_store))
            elif target not in loop.blocks:
                exits.add((name, count, has_other_store))
            else:
                pending.append((target, count, has_other_store))

    exact = bool(backedges) and all(count == 1 and not other for _, count, other in backedges)
    return {
        "condition_recognizer": condition_status,
        "selected_body": condition.body,
        "candidate_memory": memory,
        "function_wide_store_count": census["store_count_function_wide"],
        "in_loop_store_count": census["store_count_in_loop"],
        "preheader_store_count": census["store_count_in_preheader"],
        "recurrence_store_sites_in_loop": [
            {"block": name, "instruction_index": index, "step": _positive_recurrence_step(
                blocks[name].instructions[index], memory, definitions
            )}
            for name, items in events.items() for index, valid in items.items()
            if valid and name in loop.blocks
        ],
        "abstract_backedge_states": [
            {"tail": tail, "updates_saturated": count, "other_store": other}
            for tail, count, other in sorted(backedges)
        ],
        "abstract_exit_states": [
            {"tail": tail, "updates_saturated": count, "other_store": other}
            for tail, count, other in sorted(exits)
        ],
        "abstract_return_states": [
            {"block": tail, "updates_saturated": count, "other_store": other}
            for tail, count, other in sorted(returns)
        ],
        "opaque_terminators": [
            {"block": name, "opcode": opcode, "updates_saturated": count, "other_store": other}
            for name, opcode, count, other in sorted(opaque_terminators)
        ],
        "abstract_states_visited": len(visited),
        "all_reachable_abstract_backedge_states_one_update": exact,
        "probe_status": (
            "ONE_UPDATE_ON_ALL_REACHABLE_ABSTRACT_BACKEDGE_STATES"
            if exact else "NOT_PROVEN"
        ),
        "scope_note": (
            "Conservative abstract reachability over all IR branch targets; update counts saturate at 2. "
            "The result is CFG-shape evidence, not a source-level induction proof. It does not prove edge "
            "feasibility, termination, initialization semantics, bounds, alias safety, dependence, or SIMD legality."
        ),
    }


def analyze_workloads() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for workload, source_relative, function_name in WORKLOADS:
        source = (ROOT / source_relative).read_bytes()
        compilation = compile_source(source.decode("utf-8"), OptimizationLevel.O1)
        ir, _assembly = compilation.require_ordinary_artifacts()
        matching = [
            function for function in ir.functions
            if function.name == function_name or function.name.endswith(f"__{function_name}")
        ]
        if len(matching) != 1:
            raise RuntimeError(f"expected one function {function_name}; found {len(matching)}")
        function = matching[0]
        for loop in loop_analysis.discover_loop_info(function):
            rows.append({
                "workload": workload,
                "source_path": source_relative,
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "function": function.name,
                "loop_header": loop.header,
                "natural_loop_blocks": len(loop.blocks),
                **probe_loop_recurrence(function, loop),
            })
    return {
        "schema": "s3-1.11-loop-recurrence-probe-v1",
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
            "loops_with_one_update_on_all_reachable_abstract_backedge_states": sum(
                row.get("all_reachable_abstract_backedge_states_one_update", False) for row in rows
            ),
            "vectorization_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    encoded = json.dumps(analyze_workloads(), sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
