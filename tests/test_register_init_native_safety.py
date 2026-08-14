from __future__ import annotations

import platform
from pathlib import Path

import pytest

from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyParameter,
    AssemblyProgram,
    AssemblyType,
)
from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.backends.x86_64.register_init_safety import (
    proven_initialized_register_reads,
)
from bootstrap.s3.pipeline import compile_source


def _function(
    instructions: tuple[AssemblyInstruction, ...],
    register_types: tuple[tuple[int, AssemblyType], ...],
    *,
    parameters: tuple[AssemblyParameter, ...] = (),
    return_type: AssemblyType = AssemblyType.TRYTE,
) -> AssemblyFunction:
    return AssemblyFunction(
        name="main",
        return_type=return_type,
        parameters=parameters,
        register_types=register_types,
        blocks=(AssemblyBlock("entry", instructions),),
    )


def test_definite_local_write_proves_exact_register_read() -> None:
    function = _function(
        (
            AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=7),
            AssemblyInstruction(AssemblyOpcode.TRET, (0,)),
        ),
        ((0, AssemblyType.TRYTE),),
    )

    assert proven_initialized_register_reads(function) == frozenset({("entry", 1, 0)})


def test_uninitialized_register_keeps_checked_path() -> None:
    function = _function(
        (AssemblyInstruction(AssemblyOpcode.TRET, (0,)),),
        ((0, AssemblyType.TRYTE),),
    )

    assert not proven_initialized_register_reads(function)
    native = X8664Backend().generate(AssemblyProgram((function,)))
    assert "cmp byte ptr" in native


def test_join_with_uninitialized_predecessor_is_not_proven() -> None:
    function = AssemblyFunction(
        name="main",
        return_type=AssemblyType.TRYTE,
        parameters=(),
        register_types=((0, AssemblyType.TRIT), (1, AssemblyType.TRYTE)),
        blocks=(
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=0),
                    AssemblyInstruction(
                        AssemblyOpcode.TBR3,
                        (0,),
                        labels=("left", "right", "join"),
                    ),
                ),
            ),
            AssemblyBlock(
                "left",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (1,), immediate=1),
                    AssemblyInstruction(AssemblyOpcode.TJMP, labels=("join",)),
                ),
            ),
            AssemblyBlock("right", (AssemblyInstruction(AssemblyOpcode.TJMP, labels=("join",)),)),
            AssemblyBlock("join", (AssemblyInstruction(AssemblyOpcode.TRET, (1,)),)),
        ),
    )

    assert not any(site[0] == "join" for site in proven_initialized_register_reads(function))


def test_calls_are_conservatively_excluded() -> None:
    program = compile_source(
        """fn add(a: tryte, b: tryte) -> tryte:
    return a + b
fn main() -> tryte:
    return add(1, 2)
""",
        "O0",
    ).assembly
    main = next(function for function in program.functions if function.name == "main")

    assert not proven_initialized_register_reads(main)


def test_alias_reads_remain_proven_when_source_is_initialized() -> None:
    function = _function(
        (
            AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=7),
            AssemblyInstruction(AssemblyOpcode.TMOV, (1, 0)),
            AssemblyInstruction(AssemblyOpcode.TRET, (1,)),
        ),
        ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE)),
    )

    assert ("entry", 2, 1) in proven_initialized_register_reads(function)


def test_address_taken_register_is_conservatively_excluded() -> None:
    function = _function(
        (
            AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=7),
            AssemblyInstruction(
                AssemblyOpcode.TADDR,
                (1, 0),
                reference_target=AssemblyType.TRYTE,
            ),
            AssemblyInstruction(AssemblyOpcode.TRET, (0,)),
        ),
        ((0, AssemblyType.TRYTE), (1, AssemblyType.REFERENCE)),
    )

    assert not proven_initialized_register_reads(function)


def test_reference_contract_disables_local_fact() -> None:
    function = AssemblyFunction(
        name="main",
        return_type=AssemblyType.TRYTE,
        parameters=(),
        register_types=((0, AssemblyType.TRYTE),),
        reference_targets=((1, AssemblyType.TRYTE, True),),
        blocks=(
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=7),
                    AssemblyInstruction(AssemblyOpcode.TRET, (0,)),
                ),
            ),
        ),
    )

    assert not proven_initialized_register_reads(function)


def test_slice_contract_disables_local_fact() -> None:
    function = AssemblyFunction(
        name="main",
        return_type=AssemblyType.TRYTE,
        parameters=(),
        register_types=((0, AssemblyType.TRYTE), (1, AssemblyType.REFERENCE)),
        slice_registers=(1,),
        blocks=(
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=7),
                    AssemblyInstruction(AssemblyOpcode.TRET, (0,)),
                ),
            ),
        ),
    )

    assert not proven_initialized_register_reads(function)


def test_loop_fact_and_redefinition_remain_conservative_and_local() -> None:
    program = compile_source(
        """fn main() -> tryte:
    mut i: tryte = 0
    while i < 2:
        i = i + 1
    return i
""",
        "O1",
    ).assembly
    main = next(function for function in program.functions if function.name == "main")
    sites = proven_initialized_register_reads(main)

    assert sites
    assert all(block != "unreachable" for block, _, _ in sites)

    redefined = _function(
        (
            AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=1),
            AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=2),
            AssemblyInstruction(AssemblyOpcode.TRET, (0,)),
        ),
        ((0, AssemblyType.TRYTE),),
    )
    assert ("entry", 2, 0) in proven_initialized_register_reads(redefined)


def test_positive_native_shape_removes_only_initialization_check() -> None:
    function = _function(
        (
            AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=7),
            AssemblyInstruction(AssemblyOpcode.TRET, (0,)),
        ),
        ((0, AssemblyType.TRYTE),),
    )

    native = X8664Backend().generate(AssemblyProgram((function,)))

    assert "cmp byte ptr" not in native
    assert "mov qword ptr" in native or "mov rax," in native


@pytest.mark.s3_native
def test_positive_native_result_is_preserved(tmp_path: Path) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("requires Linux x86-64")
    toolchain = NativeToolchain.detect()
    program = compile_source(
        "fn main() -> tryte:\n    return 7\n",
        "O1",
    ).assembly
    executable = toolchain.build(
        X8664Backend().generate(program),
        tmp_path / "positive",
    )

    completed = toolchain.run(executable)

    assert completed.returncode == 0
    assert completed.stdout.strip() == "program returned: 7"
