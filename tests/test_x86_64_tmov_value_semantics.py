from __future__ import annotations

import platform
from pathlib import Path

import pytest

from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyMemoryObject,
    AssemblyOpcode,
    AssemblyParameter,
    AssemblyProgram,
    AssemblyType,
)
from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.emulator import Emulator, EmulatorError


def _program(
    instructions: tuple[AssemblyInstruction, ...],
    register_types: tuple[tuple[int, AssemblyType], ...],
    *,
    return_type: AssemblyType = AssemblyType.TRYTE,
    blocks: tuple[AssemblyBlock, ...] | None = None,
    parameters: tuple[AssemblyParameter, ...] = (),
    memory_objects: tuple[AssemblyMemoryObject, ...] = (),
    reference_targets: tuple[tuple[int, AssemblyType, bool], ...] = (),
    reference_storage_sizes: tuple[tuple[int, int], ...] = (),
) -> AssemblyProgram:
    function = AssemblyFunction(
        name="main",
        return_type=return_type,
        parameters=parameters,
        register_types=register_types,
        blocks=blocks or (AssemblyBlock("entry", instructions),),
        memory_objects=memory_objects,
        reference_targets=reference_targets,
        reference_storage_sizes=reference_storage_sizes,
    )
    return AssemblyProgram((function,))


def _const(register: int, value: int | float) -> AssemblyInstruction:
    return AssemblyInstruction(AssemblyOpcode.TCONST, (register,), immediate=value)


def _move(destination: int, source: int) -> AssemblyInstruction:
    return AssemblyInstruction(AssemblyOpcode.TMOV, (destination, source))


def _ret(register: int) -> AssemblyInstruction:
    return AssemblyInstruction(AssemblyOpcode.TRET, (register,))


def _straight_line_cases() -> tuple[tuple[str, AssemblyProgram, int], ...]:
    tryte = ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE))
    return (
        (
            "T01_copy_source_unchanged",
            _program((_const(0, 5), _move(1, 0), _ret(1)), tryte),
            5,
        ),
        (
            "T02_source_redefined",
            _program((_const(0, 5), _move(1, 0), _const(0, 2), _ret(1)), tryte),
            5,
        ),
        (
            "T03_destination_read_multiple_times",
            _program(
                (_const(0, 5), _move(1, 0), _const(0, 2),
                 AssemblyInstruction(AssemblyOpcode.TADD, (2, 1, 1)), _ret(2)),
                (*tryte, (2, AssemblyType.TRYTE)),
            ),
            10,
        ),
        (
            "T04_destination_redefined",
            _program((_const(0, 5), _move(1, 0), _const(1, 2), _ret(1)), tryte),
            2,
        ),
        (
            "T05_alias_chain",
            _program(
                (_const(0, 5), _move(1, 0), _move(2, 1), _const(0, 2), _ret(2)),
                (*tryte, (2, AssemblyType.TRYTE)),
            ),
            5,
        ),
        (
            "T06_source_redefined_after_alias_chain",
            _program(
                (_const(0, 5), _move(1, 0), _move(2, 1), _const(1, 2),
                 _const(0, 3), _ret(2)),
                (*tryte, (2, AssemblyType.TRYTE)),
            ),
            5,
        ),
        (
            "T18_self_move",
            _program((_const(0, 5), _move(0, 0), _ret(0)), ((0, AssemblyType.TRYTE),)),
            5,
        ),
    )


def _cfg_cases() -> tuple[tuple[str, AssemblyProgram, int], ...]:
    tryte = ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE), (2, AssemblyType.TRIT))
    return (
        (
            "T07_cross_block",
            _program(
                (), tryte,
                blocks=(
                    AssemblyBlock("entry", (_const(0, 5), AssemblyInstruction(AssemblyOpcode.TJMP, labels=("move",)))),
                    AssemblyBlock("move", (_move(1, 0), _const(0, 2), _ret(1))),
                ),
            ),
            5,
        ),
        (
            "T08_branch_source_changed_one_branch",
            _program(
                (), tryte,
                blocks=(
                    AssemblyBlock("entry", (_const(0, 5), _move(1, 0), _const(2, -1), AssemblyInstruction(AssemblyOpcode.TBR3, (2,), labels=("left", "join", "join")))),
                    AssemblyBlock("left", (_const(0, 2), AssemblyInstruction(AssemblyOpcode.TJMP, labels=("join",)))),
                    AssemblyBlock("join", (_ret(1),)),
                ),
            ),
            5,
        ),
        (
            "T09_branch_source_changed_both_branches",
            _program(
                (), tryte,
                blocks=(
                    AssemblyBlock("entry", (_const(0, 5), _move(1, 0), _const(2, -1), AssemblyInstruction(AssemblyOpcode.TBR3, (2,), labels=("left", "right", "join")))),
                    AssemblyBlock("left", (_const(0, 2), AssemblyInstruction(AssemblyOpcode.TJMP, labels=("join",)))),
                    AssemblyBlock("right", (_const(0, 3), AssemblyInstruction(AssemblyOpcode.TJMP, labels=("join",)))),
                    AssemblyBlock("join", (_ret(1),)),
                ),
            ),
            5,
        ),
        (
            "T10_join_value",
            _program(
                (), tryte,
                blocks=(
                    AssemblyBlock("entry", (_const(0, 5), _const(2, -1), AssemblyInstruction(AssemblyOpcode.TBR3, (2,), labels=("left", "join", "join")))),
                    AssemblyBlock("left", (_move(1, 0), AssemblyInstruction(AssemblyOpcode.TJMP, labels=("join",)))),
                    AssemblyBlock("join", (_const(0, 2), _ret(1))),
                ),
            ),
            5,
        ),
        (
            "T11_move_inside_loop",
            _program(
                (), ((0, AssemblyType.TRIT), (1, AssemblyType.TRYTE), (3, AssemblyType.TRYTE)),
                blocks=(
                    AssemblyBlock("entry", (_const(0, -1), _const(1, 5), AssemblyInstruction(AssemblyOpcode.TJMP, labels=("header",)))),
                    AssemblyBlock("header", (AssemblyInstruction(AssemblyOpcode.TBR3, (0,), labels=("body", "exit", "exit")),)),
                    AssemblyBlock("body", (_move(3, 1), _const(0, 0), AssemblyInstruction(AssemblyOpcode.TJMP, labels=("header",)))),
                    AssemblyBlock("exit", (_ret(3),)),
                ),
            ),
            5,
        ),
        (
            "T12_value_live_across_backedge",
            _program(
                (), ((0, AssemblyType.TRIT), (1, AssemblyType.TRYTE), (3, AssemblyType.TRYTE)),
                blocks=(
                    AssemblyBlock("entry", (_const(0, -1), _const(1, 7), AssemblyInstruction(AssemblyOpcode.TJMP, labels=("header",)))),
                    AssemblyBlock("header", (AssemblyInstruction(AssemblyOpcode.TBR3, (0,), labels=("body", "exit", "exit")),)),
                    AssemblyBlock("body", (_move(3, 1), _const(0, 0), AssemblyInstruction(AssemblyOpcode.TJMP, labels=("header",)))),
                    AssemblyBlock("exit", (_ret(3),)),
                ),
            ),
            7,
        ),
    )


def _call_case() -> AssemblyProgram:
    main = AssemblyFunction(
        name="main",
        return_type=AssemblyType.TRYTE,
        parameters=(),
        register_types=((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE), (2, AssemblyType.TRYTE)),
        blocks=(AssemblyBlock("entry", (_const(0, 5), _move(1, 0), AssemblyInstruction(AssemblyOpcode.TCALL, (2, 1), callee="helper"), _ret(2))),),
    )
    helper = AssemblyFunction(
        name="helper",
        return_type=AssemblyType.TRYTE,
        parameters=(AssemblyParameter(0, AssemblyType.TRYTE),),
        register_types=((1, AssemblyType.TRYTE),),
        blocks=(AssemblyBlock("entry", (_const(1, 2), AssemblyInstruction(AssemblyOpcode.TADD, (0, 0, 1)), _ret(0))),),
    )
    return AssemblyProgram((main, helper))


def _reference_case() -> AssemblyProgram:
    return _program(
        (
            _const(0, 0),
            _const(3, 9),
            AssemblyInstruction(AssemblyOpcode.TADDR, (1, 0), reference_target=AssemblyType.TRYTE, reference_mutable=True),
            _move(2, 1),
            AssemblyInstruction(AssemblyOpcode.TREFSTORE, (2, 3), reference_target=AssemblyType.TRYTE, reference_mutable=True),
            AssemblyInstruction(AssemblyOpcode.TREFLOAD, (4, 2), reference_target=AssemblyType.TRYTE),
            _ret(4),
        ),
        ((0, AssemblyType.TRYTE), (1, AssemblyType.REFERENCE), (2, AssemblyType.REFERENCE), (3, AssemblyType.TRYTE), (4, AssemblyType.TRYTE)),
        reference_targets=((1, AssemblyType.TRYTE, True), (2, AssemblyType.TRYTE, True)),
    )


@pytest.mark.parametrize("name,program,expected", (*_straight_line_cases(), *_cfg_cases()))
@pytest.mark.parametrize("register_allocation", (False, True))
def test_tmov_native_matrix(
    name: str,
    program: AssemblyProgram,
    expected: int,
    register_allocation: bool,
    tmp_path: Path,
) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("requires Linux x86-64")
    assert Emulator().execute(program) == expected
    toolchain = NativeToolchain.detect()
    assembly = X8664Backend(register_allocation=register_allocation).generate(program)
    executable = toolchain.build(assembly, tmp_path / f"{name}-{register_allocation}")
    completed = toolchain.run(executable)
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout == f"program returned: {expected}\n"


def test_tmov_call_and_residence_modes(tmp_path: Path) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("requires Linux x86-64")
    program = _call_case()
    assert Emulator().execute(program) == 7
    toolchain = NativeToolchain.detect()
    for mode in (False, True):
        assembly = X8664Backend(register_allocation=mode).generate(program)
        executable = toolchain.build(assembly, tmp_path / f"call-{mode}")
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == "program returned: 7\n"


def test_tmov_trit_tryte_i64_and_reference_contracts(tmp_path: Path) -> None:
    trit = _program((_const(0, -1), _move(1, 0), _ret(1)), ((0, AssemblyType.TRIT), (1, AssemblyType.TRIT)), return_type=AssemblyType.TRIT)
    i64 = _program((_const(0, 123456789), _move(1, 0), _ret(1)), ((0, AssemblyType.I64), (1, AssemblyType.I64)), return_type=AssemblyType.I64)
    reference = _reference_case()
    assert Emulator().execute(trit) == -1
    assert Emulator().execute(i64) == 123456789
    Emulator().validate(reference, entry="main")
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        return
    toolchain = NativeToolchain.detect()
    for name, program, expected in (("trit", trit, -1), ("i64", i64, 123456789), ("reference", reference, 9)):
        assembly = X8664Backend().generate(program)
        executable = toolchain.build(assembly, tmp_path / name)
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == f"program returned: {expected}\n"


def test_tmov_f64_value_copy_is_defined_by_emulator() -> None:
    program = _program(
        (_const(0, 1.5), _move(1, 0), _ret(1)),
        ((0, AssemblyType.F64), (1, AssemblyType.F64)),
        return_type=AssemblyType.F64,
    )
    assert Emulator().execute(program) == 1.5


def test_tmov_uninitialized_source_is_rejected() -> None:
    program = _program((_move(1, 0), _ret(1)), ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE)))
    with pytest.raises(EmulatorError, match="uninitialized"):
        Emulator().execute(program)


def test_tmov_self_move_preserves_instruction_accounting() -> None:
    program = _program((_const(0, 5), _move(0, 0), _ret(0)), ((0, AssemblyType.TRYTE),))
    assert Emulator(enable_metrics=True).execute(program) == 5
    emulator = Emulator(enable_metrics=True)
    assert emulator.execute(program) == 5
    assert emulator.metrics is not None
    assert emulator.metrics.executed_s3_opcodes == 3
