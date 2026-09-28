"""Census loop-local slice access shapes without claiming legality."""

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


def _expression_shape(
    register: int,
    definitions: dict[int, IRInstruction],
    register_types: dict[int, str],
    induction_memory: int | None,
    blocks: dict[str, Any],
    definition_sites: dict[int, tuple[str, int, IRInstruction]],
    seen: frozenset[int] = frozenset(),
) -> dict[str, Any]:
    if register in seen:
        return {"kind": "cycle", "register": register}
    instruction = definitions.get(register)
    if instruction is None:
        return {"kind": "input", "register": register, "type": register_types.get(register)}
    if instruction.opcode is IROpcode.CONST:
        return {"kind": "constant", "value": instruction.immediate}
    if instruction.opcode is IROpcode.LOAD and instruction.memory == induction_memory:
        return {"kind": "candidate_induction_load", "memory": induction_memory}
    next_seen = seen | {register}
    if instruction.opcode is IROpcode.MOVE and len(instruction.operands) == 1:
        return _expression_shape(
            instruction.operands[0], definitions, register_types,
            induction_memory, blocks, definition_sites, next_seen,
        )
    if instruction.opcode is IROpcode.CONVERT and len(instruction.operands) == 1:
        return {
            "kind": "conversion_barrier",
            "result_type": register_types.get(register),
            "source": _expression_shape(
                instruction.operands[0], definitions, register_types,
                induction_memory, blocks, definition_sites, next_seen,
            ),
            "reason": "conversion semantics must be proven before treating this as an affine access",
        }
    if instruction.opcode in {IROpcode.ADD, IROpcode.MULTIPLY} and len(instruction.operands) == 2:
        return {
            "kind": instruction.opcode.value,
            "operands": [
                _expression_shape(
                    item, definitions, register_types, induction_memory,
                    blocks, definition_sites, next_seen,
                )
                for item in instruction.operands
            ],
        }
    if instruction.opcode is IROpcode.LOAD and instruction.memory is not None:
        site = definition_sites.get(register)
        if site is not None:
            block_name, instruction_index, _load = site
            block = blocks[block_name]
            reaching = next((
                (prior_index, prior)
                for prior_index, prior in reversed(list(enumerate(block.instructions[:instruction_index])))
                if prior.opcode is IROpcode.STORE and prior.memory == instruction.memory
                and len(prior.operands) == 2
            ), None)
            if reaching is not None:
                store_index, reaching_store = reaching
                return {
                    "kind": "same_block_store_load",
                    "memory": instruction.memory,
                    "source": _expression_shape(
                        reaching_store.operands[1], definitions, register_types,
                        induction_memory, blocks, definition_sites,
                        next_seen | {register},
                    ),
                    "store_instruction_index": store_index,
                }
    return {
        "kind": "opaque_definition",
        "opcode": instruction.opcode.value,
        "result_type": register_types.get(register),
        "operands": list(instruction.operands),
    }


def _affine_shape(expression: dict[str, Any]) -> tuple[int, int] | None:
    kind = expression["kind"]
    if kind == "candidate_induction_load":
        return (1, 0)
    if kind == "constant" and isinstance(expression.get("value"), int):
        return (0, expression["value"])
    if kind == "conversion_barrier":
        return _affine_shape(expression["source"])
    if kind == "same_block_store_load":
        return _affine_shape(expression["source"])
    if kind == "add":
        left, right = (_affine_shape(item) for item in expression["operands"])
        if left is None or right is None:
            return None
        return (left[0] + right[0], left[1] + right[1])
    if kind == "multiply":
        left, right = (_affine_shape(item) for item in expression["operands"])
        if left is None or right is None:
            return None
        if left[0] == 0:
            return (right[0] * left[1], right[1] * left[1])
        if right[0] == 0:
            return (left[0] * right[1], left[1] * right[1])
    return None


def _barriers(expression: dict[str, Any]) -> list[str]:
    result: list[str] = []
    if expression["kind"] == "conversion_barrier":
        result.append(str(expression.get("result_type")))
        result.extend(_barriers(expression["source"]))
    elif expression["kind"] == "same_block_store_load":
        result.extend(_barriers(expression["source"]))
    elif expression["kind"] in {"add", "multiply"}:
        for operand in expression["operands"]:
            result.extend(_barriers(operand))
    return result


def _access_row(
    block: str,
    index: int,
    instruction: IRInstruction,
    definitions: dict[int, IRInstruction],
    register_types: dict[int, str],
    induction_memory: int | None,
    blocks: dict[str, Any],
    definition_sites: dict[int, tuple[str, int, IRInstruction]],
    parameters: dict[int, Any],
) -> dict[str, Any]:
    is_store = instruction.opcode is IROpcode.SLICE_STORE
    expected_operands = 4 if is_store else 3
    if len(instruction.operands) != expected_operands:
        return {
            "block": block,
            "instruction_index": index,
            "opcode": instruction.opcode.value,
            "status": "UNEXPECTED_OPERAND_SHAPE",
            "operands": list(instruction.operands),
        }
    base, length = instruction.operands[:2]
    index_register = instruction.operands[2]
    expression = _expression_shape(
        index_register, definitions, register_types, induction_memory,
        blocks, definition_sites,
    )
    affine = _affine_shape(expression)
    parameter = parameters.get(base)
    return {
        "block": block,
        "instruction_index": index,
        "opcode": instruction.opcode.value,
        "direction": "WRITE" if is_store else "READ",
        "base_register": base,
        "base_parameter": parameter.name if parameter is not None else None,
        "length_register": length,
        "index_expression": expression,
        "affine_shape_ignoring_conversion_barriers": (
            {"coefficient": affine[0], "offset": affine[1]} if affine is not None else None
        ),
        "conversion_barriers": _barriers(expression),
        "bounds_status": "UNKNOWN",
        "dependence_status": "UNKNOWN",
    }


def analyze_workloads() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for workload, source_path, function_name in WORKLOADS:
        source = (ROOT / source_path).read_bytes()
        compilation = compile_source(source.decode("utf-8"), OptimizationLevel.O1)
        ir, _assembly = compilation.require_ordinary_artifacts()
        matching = [
            function for function in ir.functions
            if function.name == function_name or function.name.endswith(f"__{function_name}")
        ]
        if len(matching) != 1:
            raise RuntimeError(f"expected one function {function_name}; found {len(matching)}")
        function = matching[0]
        definitions = _definitions(function)
        blocks = {block.name: block for block in function.blocks}
        definition_sites = {
            result: (block.name, index, instruction)
            for block in function.blocks
            for index, instruction in enumerate(block.instructions)
            for result in instruction.results
        }
        register_types = {register.index: register.type.value for register in function.registers}
        parameters = {parameter.register: parameter for parameter in function.parameters}
        for loop in loop_analysis.discover_loop_info(function):
            _condition_status, condition = _condition_diagnostic(function, loop.header, definitions)
            if condition is not None and (
                condition.body not in loop.blocks
                or condition.join not in loop.blocks
                or any(arm not in loop.blocks for arm in condition.relation_arms)
            ):
                condition = None
            census = _induction_memory_census(function, loop, definitions)
            memory = census["candidate_memory"]
            accesses = [
                _access_row(block.name, instruction_index, instruction, definitions,
                            register_types, memory, blocks, definition_sites, parameters)
                for block in function.blocks if block.name in loop.blocks
                for instruction_index, instruction in enumerate(block.instructions)
                if instruction.opcode in {IROpcode.SLICE_LOAD, IROpcode.SLICE_STORE}
            ]
            access_counts = Counter(
                (item.get("opcode"), item.get("direction")) for item in accesses
            )
            rows.append({
                "workload": workload,
                "source_path": source_path,
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "function": function.name,
                "loop_header": loop.header,
                "natural_loop_blocks": len(loop.blocks),
                "candidate_induction_memory": memory,
                "condition_body": condition.body if condition is not None else None,
                "slice_access_counts": {
                    f"{opcode}:{direction}": count
                    for (opcode, direction), count in sorted(access_counts.items())
                },
                "slice_accesses": accesses,
                "all_bounds_unknown": all(item.get("bounds_status") == "UNKNOWN" for item in accesses),
                "all_dependence_unknown": all(item.get("dependence_status") == "UNKNOWN" for item in accesses),
                "interpretation": (
                    "Affine forms ignore conversion barriers only to reveal expression shape; they do not prove "
                    "overflow behavior, bounds, aliasing, dependence, or vector legality."
                ),
            })
    return {
        "schema": "s3-1.11-loop-access-shapes-v1",
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
            "loops_with_slice_accesses": sum(bool(row["slice_accesses"]) for row in rows),
            "access_bounds_proven": 0,
            "dependence_proofs": 0,
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
