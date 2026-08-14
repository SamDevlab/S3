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
from bootstrap.s3.assembly_verifier import AssemblyVerifier
from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.backends.x86_64.liveness import InstructionSite, analyze_liveness
from bootstrap.s3.backends.x86_64.register_init_safety import (
    proven_initialized_register_reads,
)
from bootstrap.s3.emulator import Emulator, EmulatorError


def _shared_read_program() -> AssemblyProgram:
    shared_return = AssemblyInstruction(AssemblyOpcode.TRET, (1,))
    function = AssemblyFunction(
        name="main",
        return_type=AssemblyType.TRYTE,
        parameters=(),
        register_types=((0, AssemblyType.TRIT), (1, AssemblyType.TRYTE)),
        blocks=(
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=-1),
                    AssemblyInstruction(
                        AssemblyOpcode.TBR3,
                        (0,),
                        labels=("unsafe", "other", "safe"),
                    ),
                ),
            ),
            AssemblyBlock("unsafe", (shared_return,)),
            AssemblyBlock(
                "other",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (1,), immediate=0),
                    AssemblyInstruction(AssemblyOpcode.TRET, (1,)),
                ),
            ),
            AssemblyBlock(
                "safe",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (1,), immediate=7),
                    shared_return,
                ),
            ),
        ),
    )
    return AssemblyProgram((function,))


def _shared_call_function() -> AssemblyFunction:
    shared_call = AssemblyInstruction(
        AssemblyOpcode.TCALL,
        (2, 0),
        callee="helper",
    )
    return AssemblyFunction(
        name="main",
        return_type=AssemblyType.TRYTE,
        parameters=(),
        register_types=(
            (0, AssemblyType.TRIT),
            (1, AssemblyType.TRYTE),
            (2, AssemblyType.TRYTE),
        ),
        blocks=(
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=-1),
                    AssemblyInstruction(
                        AssemblyOpcode.TBR3,
                        (0,),
                        labels=("live", "other", "dead"),
                    ),
                ),
            ),
            AssemblyBlock(
                "live",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (1,), immediate=7),
                    shared_call,
                    AssemblyInstruction(AssemblyOpcode.TRET, (1,)),
                ),
            ),
            AssemblyBlock(
                "other",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (1,), immediate=0),
                    AssemblyInstruction(AssemblyOpcode.TRET, (1,)),
                ),
            ),
            AssemblyBlock(
                "dead",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (1,), immediate=7),
                    shared_call,
                    AssemblyInstruction(AssemblyOpcode.TRET, (2,)),
                ),
            ),
        ),
    )


def _shared_call_program() -> AssemblyProgram:
    helper = AssemblyFunction(
        name="helper",
        return_type=AssemblyType.TRYTE,
        parameters=(AssemblyParameter(0, AssemblyType.TRYTE),),
        register_types=(),
        blocks=(
            AssemblyBlock(
                "entry",
                (AssemblyInstruction(AssemblyOpcode.TRET, (0,)),),
            ),
        ),
    )
    return AssemblyProgram((helper, _shared_call_function()))


def test_shared_instruction_is_validated_and_safe_read_is_site_specific() -> None:
    program = _shared_read_program()
    function = program.functions[0]

    AssemblyVerifier().validate(program, entry="main")
    sites = proven_initialized_register_reads(function)

    assert ("unsafe", 0, 1) not in sites
    assert ("safe", 1, 1) in sites
    with pytest.raises(EmulatorError, match="uninitialized register r1"):
        Emulator().execute(program)

    for register_allocation in (False, True):
        first = X8664Backend(register_allocation=register_allocation).generate(program)
        second = X8664Backend(register_allocation=register_allocation).generate(program)
        assert first == second
        unsafe = first.split("_unsafe:", 1)[1].split("_other:", 1)[0]
        assert "cmp byte ptr" in unsafe


def test_shared_call_uses_structural_liveness_sites() -> None:
    program = _shared_call_program()
    function = program.functions[1]
    liveness = analyze_liveness(function)
    live_site = InstructionSite("live", 1)
    dead_site = InstructionSite("dead", 1)

    assert liveness.live_across_call(live_site) == frozenset({1})
    assert liveness.live_across_call(dead_site) == frozenset()

    plan = analyze_allocation(function)
    assert plan.call_survivors_for(live_site) == frozenset({1})
    assert plan.call_survivors_for(dead_site) == frozenset()


@pytest.mark.s3_native
@pytest.mark.parametrize("register_allocation", (False, True))
def test_shared_read_native_matches_emulator_failure(
    register_allocation: bool,
    tmp_path: Path,
) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        pytest.skip("requires Linux x86-64")
    toolchain = NativeToolchain.detect()
    native = X8664Backend(register_allocation=register_allocation).generate(
        _shared_read_program()
    )
    executable = toolchain.build(native, tmp_path / f"shared-read-{register_allocation}")
    completed = toolchain.run(executable)

    assert completed.returncode != 0
    assert completed.returncode not in {-11, 139}
    assert "uninitialized register" in completed.stderr.lower()
