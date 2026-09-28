from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from bootstrap.s3.ir import IRBasicBlock, IROpcode, IRModule
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa_optimizer.loops import discover_loop_info
from tools.s3_111_loop_memory_dependence import (
    WORKLOADS,
    analyze_workloads,
    classify_loop_slice_effects,
)


def _compiled(workload_name: str):
    workload, source_path, function_name = next(
        row for row in WORKLOADS if row[0] == workload_name
    )
    compilation = compile_source(
        Path(source_path).read_text(encoding="utf-8"),
        OptimizationLevel.O1,
    )
    module, _assembly = compilation.require_ordinary_artifacts()
    function = next(
        item for item in module.functions
        if item.name == function_name or item.name.endswith(f"__{function_name}")
    )
    return workload, module, function


def test_pinned_loops_prove_only_read_only_slice_memory() -> None:
    report = analyze_workloads()
    assert report["summary"] == {
        "loops": 5,
        "read_only_slice_memory_proven": 5,
        "slice_write_dependence_proven_absent": 5,
        "whole_loop_independence_proven": 0,
        "vectorization_authorized": False,
    }
    assert all(row["whole_loop_independence"] == "NOT_PROVEN" for row in report["loops"])
    assert all(row["local_scalar_store_count"] > 0 for row in report["loops"])


def test_slice_store_invalidates_read_only_dependence_result() -> None:
    _workload, module, function = _compiled("point-cloud")
    loop = discover_loop_info(function)[0]
    target_name = next(
        block.name for block in function.blocks
        if block.name in loop.blocks
        and any(item.opcode is IROpcode.SLICE_LOAD for item in block.instructions)
    )
    blocks = []
    for block in function.blocks:
        if block.name != target_name:
            blocks.append(block)
            continue
        load = next(item for item in block.instructions if item.opcode is IROpcode.SLICE_LOAD)
        injected = replace(load, opcode=IROpcode.SLICE_STORE, operands=(*load.operands, load.results[0]), results=(), result=None)
        instructions = list(block.instructions)
        insertion = next(
            index for index, item in enumerate(instructions)
            if item.opcode in {IROpcode.JUMP, IROpcode.BRANCH3, IROpcode.RETURN}
        )
        instructions.insert(insertion, injected)
        blocks.append(replace(block, instructions=tuple(instructions)))
    mutated_function = replace(function, blocks=tuple(blocks))
    mutated_module = replace(
        module,
        functions=tuple(mutated_function if item.name == function.name else item for item in module.functions),
    )
    mutated_loop = next(item for item in discover_loop_info(mutated_function) if item.header == loop.header)

    row = classify_loop_slice_effects(mutated_module, mutated_function, mutated_loop)

    assert row["status"] == "UNKNOWN"
    assert row["slice_store_count"] == 1
    assert row["vectorization_authorized"] is False


def test_unresolved_loop_call_fails_closed() -> None:
    _workload, module, function = _compiled("energy")
    loop = discover_loop_info(function)[0]
    blocks = []
    for block in function.blocks:
        instructions = tuple(
            replace(item, callee="unknown_external_effect")
            if block.name in loop.blocks and item.opcode is IROpcode.CALL
            else item
            for item in block.instructions
        )
        blocks.append(replace(block, instructions=instructions))
    mutated_function = replace(function, blocks=tuple(blocks))
    mutated_module = replace(
        module,
        functions=tuple(mutated_function if item.name == function.name else item for item in module.functions),
    )
    mutated_loop = next(item for item in discover_loop_info(mutated_function) if item.header == loop.header)

    row = classify_loop_slice_effects(mutated_module, mutated_function, mutated_loop)

    assert row["status"] == "UNKNOWN"
    assert any("unresolved or mutating call" in reason for reason in row["reasons"])
