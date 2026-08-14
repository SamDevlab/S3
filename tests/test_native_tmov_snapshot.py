from __future__ import annotations

import platform
from pathlib import Path

import pytest

from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
)
from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.emulator import Emulator


def _single_block_program(
    instructions: tuple[AssemblyInstruction, ...],
    register_types: tuple[tuple[int, AssemblyType], ...],
) -> AssemblyProgram:
    return AssemblyProgram(
        (
            AssemblyFunction(
                name="main",
                return_type=AssemblyType.TRYTE,
                parameters=(),
                register_types=register_types,
                blocks=(AssemblyBlock("entry", instructions),),
            ),
        )
    )


def _cases() -> tuple[tuple[str, AssemblyProgram, int], ...]:
    return (
        (
            "source_redefinition",
            _single_block_program(
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=1),
                    AssemblyInstruction(AssemblyOpcode.TMOV, (1, 0)),
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=2),
                    AssemblyInstruction(AssemblyOpcode.TRET, (1,)),
                ),
                ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE)),
            ),
            1,
        ),
        (
            "destination_redefinition",
            _single_block_program(
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=1),
                    AssemblyInstruction(AssemblyOpcode.TMOV, (1, 0)),
                    AssemblyInstruction(AssemblyOpcode.TCONST, (1,), immediate=2),
                    AssemblyInstruction(AssemblyOpcode.TRET, (1,)),
                ),
                ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE)),
            ),
            2,
        ),
        (
            "transitive_alias",
            _single_block_program(
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=1),
                    AssemblyInstruction(AssemblyOpcode.TMOV, (1, 0)),
                    AssemblyInstruction(AssemblyOpcode.TMOV, (2, 1)),
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=2),
                    AssemblyInstruction(AssemblyOpcode.TRET, (2,)),
                ),
                (
                    (0, AssemblyType.TRYTE),
                    (1, AssemblyType.TRYTE),
                    (2, AssemblyType.TRYTE),
                ),
            ),
            1,
        ),
        (
            "independent_aliases",
            _single_block_program(
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=1),
                    AssemblyInstruction(AssemblyOpcode.TMOV, (1, 0)),
                    AssemblyInstruction(AssemblyOpcode.TMOV, (2, 0)),
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=2),
                    AssemblyInstruction(AssemblyOpcode.TADD, (3, 1, 2)),
                    AssemblyInstruction(AssemblyOpcode.TRET, (3,)),
                ),
                (
                    (0, AssemblyType.TRYTE),
                    (1, AssemblyType.TRYTE),
                    (2, AssemblyType.TRYTE),
                    (3, AssemblyType.TRYTE),
                ),
            ),
            2,
        ),
        (
            "no_redefinition",
            _single_block_program(
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=3),
                    AssemblyInstruction(AssemblyOpcode.TMOV, (1, 0)),
                    AssemblyInstruction(AssemblyOpcode.TRET, (1,)),
                ),
                ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE)),
            ),
            3,
        ),
        (
            "multiple_redefinitions",
            _single_block_program(
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=1),
                    AssemblyInstruction(AssemblyOpcode.TMOV, (1, 0)),
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=2),
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=3),
                    AssemblyInstruction(AssemblyOpcode.TRET, (1,)),
                ),
                ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE)),
            ),
            1,
        ),
    )


@pytest.mark.parametrize("name,program,expected", _cases())
def test_tmov_is_a_value_snapshot(
    name: str,
    program: AssemblyProgram,
    expected: int,
) -> None:
    del name
    assert Emulator().execute(program) == expected


def _branch_boundary_program() -> AssemblyProgram:
    function = AssemblyFunction(
        name="main",
        return_type=AssemblyType.TRYTE,
        parameters=(),
        register_types=(
            (0, AssemblyType.TRYTE),
            (1, AssemblyType.TRYTE),
            (2, AssemblyType.TRIT),
        ),
        blocks=(
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=1),
                    AssemblyInstruction(AssemblyOpcode.TCONST, (2,), immediate=-1),
                    AssemblyInstruction(
                        AssemblyOpcode.TBR3,
                        (2,),
                        labels=("left", "middle", "right"),
                    ),
                ),
            ),
            AssemblyBlock(
                "left",
                (
                    AssemblyInstruction(AssemblyOpcode.TMOV, (1, 0)),
                    AssemblyInstruction(AssemblyOpcode.TJMP, labels=("join",)),
                ),
            ),
            AssemblyBlock(
                "middle",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (1,), immediate=0),
                    AssemblyInstruction(AssemblyOpcode.TJMP, labels=("join",)),
                ),
            ),
            AssemblyBlock(
                "right",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (1,), immediate=0),
                    AssemblyInstruction(AssemblyOpcode.TJMP, labels=("join",)),
                ),
            ),
            AssemblyBlock("join", (AssemblyInstruction(AssemblyOpcode.TRET, (1,)),)),
        ),
    )
    return AssemblyProgram((function,))


def test_tmov_snapshot_survives_block_boundary() -> None:
    assert Emulator().execute(_branch_boundary_program()) == 1


@pytest.mark.s3_native
@pytest.mark.parametrize("register_allocation", (False, True))
@pytest.mark.parametrize(
    "name,program,expected",
    (*_cases(), ("branch_boundary", _branch_boundary_program(), 1)),
)
def test_tmov_native_matches_emulator(
    name: str,
    program: AssemblyProgram,
    expected: int,
    register_allocation: bool,
    tmp_path: Path,
) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        pytest.skip("requires Linux x86-64")
    toolchain = NativeToolchain.detect()
    native = X8664Backend(register_allocation=register_allocation).generate(program)
    executable = toolchain.build(
        native,
        tmp_path / f"tmov-{name}-{register_allocation}",
    )
    completed = toolchain.run(executable)

    assert completed.returncode == 0
    assert completed.stdout.strip() == f"program returned: {expected}"
