from __future__ import annotations

from dataclasses import replace

import pytest

from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.initialization import (
    InitializationAnalysisError,
    InitializationState,
    analyze_initialization,
)
from bootstrap.s3.ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRMemoryObject,
    IRModule,
    IROpcode,
    IRParameter,
    IRRegister,
    IRType,
)


def _linear_memory_module(
    *,
    store: bool,
    immutable: bool = False,
    duplicate: bool = False,
    calculated_index: bool = False,
) -> IRModule:
    registers = [
        IRRegister(0, IRType.TRYTE),
        IRRegister(1, IRType.TRYTE),
    ]
    instructions = [
        IRInstruction(IROpcode.CONST, result=0, immediate=1),
        IRInstruction(IROpcode.CONST, result=1, immediate=7),
    ]
    index = 0
    if calculated_index:
        registers.extend(
            (IRRegister(2, IRType.TRYTE), IRRegister(3, IRType.TRYTE))
        )
        instructions.extend(
            (
                IRInstruction(IROpcode.MOVE, result=2, operands=(0,)),
                IRInstruction(
                    IROpcode.ADD,
                    result=3,
                    operands=(0, 2),
                ),
            )
        )
        index = 3
    if store:
        instructions.append(
            IRInstruction(
                IROpcode.STORE,
                operands=(index, 1),
                memory=0,
                initialization=True,
            )
        )
        if duplicate:
            instructions.append(
                IRInstruction(
                    IROpcode.STORE,
                    operands=(index, 1),
                    memory=0,
                    initialization=True,
                )
            )
    result = max(register.index for register in registers) + 1
    registers.append(IRRegister(result, IRType.TRYTE))
    instructions.extend(
        (
            IRInstruction(
                IROpcode.LOAD,
                result=result,
                operands=(index,),
                memory=0,
            ),
            IRInstruction(IROpcode.RETURN, operands=(result,)),
        )
    )
    return IRModule(
        (
            IRFunction(
                "main",
                (),
                IRType.TRYTE,
                tuple(registers),
                (IRBasicBlock("entry", tuple(instructions)),),
                memory_objects=(
                    IRMemoryObject(0, IRType.TRYTE, 3, not immutable),
                ),
            ),
        )
    )


def _branch_memory_module(storing_branches: set[str]) -> IRModule:
    branch_names = ("negative", "zero", "positive")
    branch_blocks = tuple(
        IRBasicBlock(
            name,
            (
                *(
                    (
                        IRInstruction(
                            IROpcode.STORE,
                            operands=(1, 2),
                            memory=0,
                            initialization=True,
                        ),
                    )
                    if name in storing_branches
                    else ()
                ),
                IRInstruction(IROpcode.JUMP, targets=("join",)),
            ),
        )
        for name in branch_names
    )
    return IRModule(
        (
            IRFunction(
                "choose",
                (IRParameter("condition", 0, IRType.TRIT),),
                IRType.TRYTE,
                (
                    IRRegister(0, IRType.TRIT),
                    IRRegister(1, IRType.TRYTE),
                    IRRegister(2, IRType.TRYTE),
                    IRRegister(3, IRType.TRYTE),
                ),
                (
                    IRBasicBlock(
                        "entry",
                        (
                            IRInstruction(
                                IROpcode.CONST,
                                result=1,
                                immediate=0,
                            ),
                            IRInstruction(
                                IROpcode.CONST,
                                result=2,
                                immediate=9,
                            ),
                            IRInstruction(
                                IROpcode.BRANCH3,
                                operands=(0,),
                                targets=branch_names,
                            ),
                        ),
                    ),
                    *branch_blocks,
                    IRBasicBlock(
                        "join",
                        (
                            IRInstruction(
                                IROpcode.LOAD,
                                result=3,
                                operands=(1,),
                                memory=0,
                            ),
                            IRInstruction(IROpcode.RETURN, operands=(3,)),
                        ),
                    ),
                ),
                memory_objects=(
                    IRMemoryObject(0, IRType.TRYTE, 1, False),
                ),
            ),
        )
    )


def test_definitely_initialized_constant_and_calculated_indices_pass() -> None:
    analyze_initialization(_linear_memory_module(store=True))
    calculated = _linear_memory_module(
        store=True,
        calculated_index=True,
    )
    report = analyze_initialization(calculated)
    constants = dict(report.functions[0].constants)
    assert constants[3] == 2
    assert "TLOAD" in generate_assembly(calculated).render()


def test_definitely_uninitialized_load_is_static_error() -> None:
    module = _linear_memory_module(store=False)
    with pytest.raises(
        InitializationAnalysisError,
        match="memory m0 index 1 is definitely uninitialized",
    ):
        analyze_initialization(module)
    with pytest.raises(InitializationAnalysisError):
        generate_assembly(module)


def test_initialization_in_all_ternary_branches_is_definite() -> None:
    report = analyze_initialization(
        _branch_memory_module({"negative", "zero", "positive"})
    )
    entries = dict(report.functions[0].entry_states)
    join = dict(entries["join"])
    assert join[(0, 0)] == InitializationState.INITIALIZED.value


@pytest.mark.parametrize(
    "branches",
    (
        {"negative"},
        {"negative", "zero"},
    ),
)
def test_partial_branch_initialization_remains_runtime_checked(
    branches: set[str],
) -> None:
    module = _branch_memory_module(branches)
    report = analyze_initialization(module)
    join = dict(dict(report.functions[0].entry_states)["join"])
    assert join[(0, 0)] == InitializationState.MAYBE_INITIALIZED.value
    assert "TLOAD" in generate_assembly(module).render()


def test_no_branch_initialization_is_static_error() -> None:
    with pytest.raises(
        InitializationAnalysisError,
        match="definitely uninitialized",
    ):
        analyze_initialization(_branch_memory_module(set()))


def test_dynamic_index_is_conservative() -> None:
    module = IRModule(
        (
            IRFunction(
                "read",
                (IRParameter("index", 0, IRType.TRYTE),),
                IRType.TRYTE,
                (
                    IRRegister(0, IRType.TRYTE),
                    IRRegister(1, IRType.TRYTE),
                ),
                (
                    IRBasicBlock(
                        "entry",
                        (
                            IRInstruction(
                                IROpcode.LOAD,
                                result=1,
                                operands=(0,),
                                memory=0,
                            ),
                            IRInstruction(IROpcode.RETURN, operands=(1,)),
                        ),
                    ),
                ),
                memory_objects=(
                    IRMemoryObject(0, IRType.TRYTE, 2, True),
                ),
            ),
        )
    )
    analyze_initialization(module)
    assert "TLOAD" in generate_assembly(module).render()


def test_definite_second_immutable_store_is_static_error() -> None:
    with pytest.raises(
        InitializationAnalysisError,
        match="definitely already initialized",
    ):
        analyze_initialization(
            _linear_memory_module(
                store=True,
                immutable=True,
                duplicate=True,
            )
        )


def test_uncertain_second_immutable_store_remains_runtime_checked() -> None:
    module = _branch_memory_module({"negative"})
    function = module.functions[0]
    join = function.blocks[-1]
    uncertain_join = replace(
        join,
        instructions=(
            IRInstruction(
                IROpcode.STORE,
                operands=(1, 2),
                memory=0,
                initialization=True,
            ),
            IRInstruction(IROpcode.RETURN, operands=(2,)),
        ),
    )
    module = IRModule(
        (
            replace(
                function,
                registers=function.registers[:-1],
                blocks=(*function.blocks[:-1], uncertain_join),
            ),
        )
    )
    analyze_initialization(module)
    rendered = generate_assembly(module).render()
    assert rendered.count("TSTORE") == 2


def test_loop_analysis_reaches_fixed_point() -> None:
    module = IRModule(
        (
            IRFunction(
                "looping",
                (IRParameter("condition", 0, IRType.TRIT),),
                IRType.TRYTE,
                (
                    IRRegister(0, IRType.TRIT),
                    IRRegister(1, IRType.TRYTE),
                    IRRegister(2, IRType.TRYTE),
                    IRRegister(3, IRType.TRYTE),
                ),
                (
                    IRBasicBlock(
                        "entry",
                        (
                            IRInstruction(
                                IROpcode.CONST,
                                result=1,
                                immediate=0,
                            ),
                            IRInstruction(
                                IROpcode.CONST,
                                result=2,
                                immediate=4,
                            ),
                            IRInstruction(
                                IROpcode.STORE,
                                operands=(1, 2),
                                memory=0,
                                initialization=True,
                            ),
                            IRInstruction(
                                IROpcode.JUMP,
                                targets=("loop",),
                            ),
                        ),
                    ),
                    IRBasicBlock(
                        "loop",
                        (
                            IRInstruction(
                                IROpcode.LOAD,
                                result=3,
                                operands=(1,),
                                memory=0,
                            ),
                            IRInstruction(
                                IROpcode.BRANCH3,
                                operands=(0,),
                                targets=("again", "done", "forward"),
                            ),
                        ),
                    ),
                    IRBasicBlock(
                        "again",
                        (IRInstruction(IROpcode.JUMP, targets=("loop",)),),
                    ),
                    IRBasicBlock(
                        "forward",
                        (IRInstruction(IROpcode.JUMP, targets=("done",)),),
                    ),
                    IRBasicBlock(
                        "done",
                        (IRInstruction(IROpcode.RETURN, operands=(3,)),),
                    ),
                ),
                memory_objects=(
                    IRMemoryObject(0, IRType.TRYTE, 1, True),
                ),
            ),
        )
    )
    report = analyze_initialization(module)
    loop_entry = dict(dict(report.functions[0].entry_states)["loop"])
    assert loop_entry[(0, 0)] == InitializationState.INITIALIZED.value
