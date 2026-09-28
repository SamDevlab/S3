"""Prove a narrow read-only slice-memory fact for pinned loop workloads."""

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

from bootstrap.s3.builtin_effects import BuiltinEffect, builtin_effect
from bootstrap.s3.ir import IRFunction, IRInstruction, IRModule, IROpcode, IRType
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa_optimizer.loops import discover_loop_info
from tools.s3_111_loop_predicate_diagnostics import WORKLOADS

_REFERENCE_OPERATIONS = {
    IROpcode.ADDRESS_OF,
    IROpcode.AGGREGATE_ADDRESS_OF,
    IROpcode.AGGREGATE_FIELD_ADDRESS,
    IROpcode.AGGREGATE_FIELD_LOAD,
    IROpcode.REFERENCE_LOAD,
    IROpcode.REFERENCE_STORE,
}


def _register_types(function: IRFunction) -> dict[int, IRType]:
    return {item.index: item.type for item in function.registers} | {
        item.register: item.type for item in function.parameters
    }


def _local_call_closure(
    module: IRModule,
    caller: IRFunction,
    instruction: IRInstruction,
) -> tuple[bool, list[str], str | None]:
    """Accept only closed scalar-only local callees or known non-mutating builtins."""
    caller_types = _register_types(caller)
    callees = [item for item in module.functions if item.name == instruction.callee]
    if not callees:
        effect = builtin_effect(instruction.callee)
        if effect in {BuiltinEffect.PURE, BuiltinEffect.READ_ONLY}:
            return True, [], None
        return False, [], f"unresolved or mutating call: {instruction.callee} ({effect.value})"
    if len(callees) != 1:
        return False, [], f"callee name is ambiguous: {instruction.callee}"

    callee = callees[0]
    if callee.external:
        return False, [callee.name], f"callee body is unavailable: {callee.name}"
    if len(instruction.operands) != len(callee.parameters):
        return False, [callee.name], f"call arity disagrees with {callee.name} signature"
    for operand, parameter in zip(instruction.operands, callee.parameters, strict=True):
        if caller_types.get(operand) is not parameter.type:
            return False, [callee.name], f"call argument type is unresolved for {callee.name}"
    if any(item.type is IRType.REFERENCE for item in callee.parameters) or any(
        item.type is IRType.REFERENCE for item in callee.registers
    ) or any(item is IRType.REFERENCE for item in callee.result_types):
        return False, [callee.name], f"callee carries reference state: {callee.name}"

    memory_ids = {item.index for item in callee.memory_objects}
    nested_names: list[str] = [callee.name]
    for block in callee.blocks:
        for operation in block.instructions:
            if operation.opcode in _REFERENCE_OPERATIONS or operation.opcode in {
                IROpcode.SLICE_LENGTH,
                IROpcode.SLICE_LOAD,
                IROpcode.SLICE_STORE,
            }:
                return False, nested_names, f"callee accesses reference storage: {callee.name}"
            if operation.opcode in {IROpcode.LOAD, IROpcode.STORE} and operation.memory not in memory_ids:
                return False, nested_names, f"callee uses unmodeled memory: {callee.name}"
            if operation.opcode is IROpcode.CALL:
                ok, nested, reason = _local_call_closure(module, callee, operation)
                nested_names.extend(nested)
                if not ok:
                    return False, nested_names, reason
    return True, nested_names, None


def classify_loop_slice_effects(
    module: IRModule,
    function: IRFunction,
    loop: Any,
) -> dict[str, Any]:
    """Classify only loop-region effects on slice/reference storage."""
    blocks = {block.name: block for block in function.blocks}
    local_memory_ids = {item.index for item in function.memory_objects}
    register_types = _register_types(function)
    slice_loads: list[dict[str, Any]] = []
    slice_stores: list[dict[str, Any]] = []
    reference_stores: list[dict[str, Any]] = []
    local_stores = 0
    calls: list[dict[str, Any]] = []
    reasons: list[str] = []

    for block_name in sorted(loop.blocks):
        for index, instruction in enumerate(blocks[block_name].instructions):
            if instruction.opcode is IROpcode.SLICE_LOAD:
                base = instruction.operands[0] if instruction.operands else None
                parameter = next(
                    (item.name for item in function.parameters if item.register == base), None
                )
                slice_loads.append({
                    "block": block_name,
                    "instruction_index": index,
                    "parameter": parameter,
                })
            elif instruction.opcode is IROpcode.SLICE_STORE:
                slice_stores.append({"block": block_name, "instruction_index": index})
            elif instruction.opcode is IROpcode.REFERENCE_STORE:
                reference_stores.append({"block": block_name, "instruction_index": index})
            elif instruction.opcode is IROpcode.STORE:
                local_stores += 1
                if instruction.memory not in local_memory_ids:
                    reasons.append(f"unmodeled STORE memory at {block_name}:{index}")
                if len(instruction.operands) == 2 and register_types.get(instruction.operands[1]) is IRType.REFERENCE:
                    reasons.append(f"reference stored into opaque local memory at {block_name}:{index}")
            elif instruction.opcode is IROpcode.LOAD:
                if instruction.memory not in local_memory_ids:
                    reasons.append(f"unmodeled LOAD memory at {block_name}:{index}")
                if instruction.results and register_types.get(instruction.results[0]) is IRType.REFERENCE:
                    reasons.append(f"reference loaded from opaque local memory at {block_name}:{index}")
            elif instruction.opcode in _REFERENCE_OPERATIONS:
                reasons.append(f"unsupported reference operation {instruction.opcode.value} at {block_name}:{index}")
            elif instruction.opcode is IROpcode.CALL:
                ok, closure, reason = _local_call_closure(module, function, instruction)
                calls.append({
                    "block": block_name,
                    "instruction_index": index,
                    "callee": instruction.callee,
                    "effect_closure": closure,
                    "effect_closure_status": "PASS" if ok else "UNKNOWN",
                })
                if not ok:
                    reasons.append(reason or f"unknown call effect at {block_name}:{index}")

    if slice_stores:
        reasons.append("loop contains slice writes")
    if reference_stores:
        reasons.append("loop contains reference writes")
    passed = not reasons
    return {
        "workload_function": function.name,
        "loop_header": loop.header,
        "loop_blocks": len(loop.blocks),
        "slice_loads": slice_loads,
        "slice_store_count": len(slice_stores),
        "slice_stores": slice_stores,
        "reference_store_count": len(reference_stores),
        "reference_stores": reference_stores,
        "local_scalar_store_count": local_stores,
        "calls": calls,
        "slice_memory_effect": "READ_ONLY" if passed else "UNKNOWN_OR_WRITES",
        "slice_write_dependence": "NO_LOOP_CARRIED_SLICE_WRITE_DEPENDENCE" if passed else "NOT_PROVEN",
        "whole_loop_independence": "NOT_PROVEN",
        "vectorization_authorized": False,
        "status": "PASS" if passed else "UNKNOWN",
        "reasons": reasons,
        "scope": (
            "No loop-carried write dependence on slice/reference storage is proven only for this exact IR. "
            "Scalar induction/accumulator stores, branch feasibility, strict-FP reductions, and complete "
            "iteration independence are outside this result. Read-only parameter aliasing is not a conflict."
        ),
    }


def analyze_workloads() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for workload, source_path, function_name in WORKLOADS:
        source_bytes = (ROOT / source_path).read_bytes().replace(b"\r\n", b"\n")
        compilation = compile_source(source_bytes.decode("utf-8"), OptimizationLevel.O1)
        module, _assembly = compilation.require_ordinary_artifacts()
        functions = [
            item for item in module.functions
            if item.name == function_name or item.name.endswith(f"__{function_name}")
        ]
        if len(functions) != 1:
            raise RuntimeError(f"expected one {function_name}; found {len(functions)}")
        function = functions[0]
        for loop in discover_loop_info(function):
            row = classify_loop_slice_effects(module, function, loop)
            row.update({"workload": workload, "source_path": source_path,
                        "source_sha256": hashlib.sha256(source_bytes).hexdigest()})
            rows.append(row)

    return {
        "schema": "s3-1.11-loop-slice-memory-dependence-v1",
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
        "analysis_tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "loops": rows,
        "summary": {
            "loops": len(rows),
            "read_only_slice_memory_proven": sum(row["status"] == "PASS" for row in rows),
            "slice_write_dependence_proven_absent": sum(
                row["slice_write_dependence"] == "NO_LOOP_CARRIED_SLICE_WRITE_DEPENDENCE"
                for row in rows
            ),
            "whole_loop_independence_proven": 0,
            "vectorization_authorized": False,
        },
        "limitations": [
            "This analysis is pinned to the listed source files and their O1 IR only.",
            "Local call effects are accepted only for a closed scalar-only call closure; unknown/external/reference calls fail closed.",
            "The result does not prove scalar recurrence independence, edge feasibility, floating-point reassociation, bounds, or SIMD legality.",
        ],
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
