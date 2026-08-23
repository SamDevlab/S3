from __future__ import annotations

import pytest

from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyMemoryObject,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
    parse_assembly,
)
from bootstrap.s3.backends.x86_64 import X8664Backend, generate_native_assembly
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.backends.x86_64.experimental_policy import (
    ExperimentalNativePolicyMode,
    resolve_compact_ea_canary,
)


def _indexed_program() -> AssemblyProgram:
    function = AssemblyFunction(
        name="main",
        return_type=AssemblyType.TRYTE,
        parameters=(),
        register_types=(
            (0, AssemblyType.TRYTE),
            (1, AssemblyType.TRYTE),
            (2, AssemblyType.TRYTE),
        ),
        blocks=(
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=0),
                    AssemblyInstruction(AssemblyOpcode.TCONST, (1,), immediate=7),
                    AssemblyInstruction(AssemblyOpcode.TSTORE, (0, 1), memory=0),
                    AssemblyInstruction(AssemblyOpcode.TLOAD, (2, 0), memory=0),
                    AssemblyInstruction(AssemblyOpcode.TRET, (2,)),
                ),
            ),
        ),
        memory_objects=(
            AssemblyMemoryObject(0, AssemblyType.TRYTE, length=1, mutable=True),
        ),
    )
    return AssemblyProgram((function,))


def _reference_function() -> AssemblyFunction:
    return AssemblyFunction(
        name="main",
        return_type=AssemblyType.TRYTE,
        parameters=(),
        register_types=(
            (0, AssemblyType.TRYTE),
            (1, AssemblyType.REFERENCE),
        ),
        reference_targets=((1, AssemblyType.TRYTE, True),),
        blocks=(
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=1),
                    AssemblyInstruction(
                        AssemblyOpcode.TADDR,
                        (1, 0),
                        reference_target=AssemblyType.TRYTE,
                    ),
                    AssemblyInstruction(AssemblyOpcode.TRET, (0,)),
                ),
            ),
        ),
    )


def test_default_off_is_byte_identical_to_canonical_main_path() -> None:
    program = _indexed_program()
    assert generate_native_assembly(program) == X8664Backend(
        experimental_mode="off"
    ).generate(program)


def test_canary_is_explicit_and_uses_the_existing_physical_allocation() -> None:
    program = _indexed_program()
    function = program.functions[0]
    allocation = analyze_allocation(function)
    index_physical = allocation.physical_register(0)
    assert index_physical is not None

    baseline = generate_native_assembly(program)
    canary = X8664Backend(experimental_mode="compact-ea-canary").generate(program)
    assert baseline != canary
    assert f"[rbp + {index_physical}*2" in canary


def test_canary_falls_back_for_reference_operations() -> None:
    selection = resolve_compact_ea_canary(
        _reference_function(), ExperimentalNativePolicyMode.COMPACT_EA_CANARY
    )
    assert selection.applied is False
    assert selection.reason == "canary_safety_fallback:reference_operations_present"


def test_canary_falls_back_when_index_initialization_is_unproven() -> None:
    function = _indexed_program().functions[0]
    instructions = list(function.blocks[0].instructions)
    instructions[0] = AssemblyInstruction(AssemblyOpcode.TLOAD, (2, 0), memory=0)
    function = AssemblyFunction(
        name=function.name,
        return_type=function.return_type,
        parameters=function.parameters,
        register_types=function.register_types,
        blocks=(AssemblyBlock("entry", tuple(instructions)),),
        memory_objects=function.memory_objects,
    )
    selection = resolve_compact_ea_canary(function, "compact-ea-canary")
    assert selection.applied is False
    assert selection.reason == "canary_safety_fallback:index_initialization_not_proven"


def test_unknown_mode_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported experimental native policy mode"):
        X8664Backend(experimental_mode="compact-ea-automatic")


def test_canary_does_not_change_assembly_program_or_canonical_tmov() -> None:
    program = parse_assembly(
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
        .label entry
            TCONST r0, 7
            TMOV r1, r0
            TRET r1
        .end
        """
    )
    assert program.functions[0].instructions[1].opcode is AssemblyOpcode.TMOV
    assert X8664Backend(
        experimental_mode="compact-ea-canary"
    ).generate(program) == generate_native_assembly(program)
