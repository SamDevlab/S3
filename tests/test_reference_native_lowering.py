from __future__ import annotations

import platform
from pathlib import Path
import subprocess

import pytest

from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.backends.x86_64.emitter import X8664Emitter
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
from bootstrap.s3.pipeline import compile_source


pytestmark = [pytest.mark.s3_fast, pytest.mark.s3_contract, pytest.mark.s3_differential]


@pytest.fixture(scope="module")
def native_toolchain() -> NativeToolchain:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("native reference matrix requires Linux x86-64")
    return NativeToolchain.detect()


def _run_native(source: str, optimization: str, register_allocation: bool, toolchain: NativeToolchain, tmp_path: Path) -> int:
    program = compile_source(source, optimization).assembly
    assembly = X8664Backend(register_allocation=register_allocation).generate(program)
    executable = toolchain.build(assembly, tmp_path / "reference-program")
    completed = toolchain.run(executable)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    return int(completed.stdout.strip())


def _reference_program() -> AssemblyProgram:
    function = AssemblyFunction(
        "main",
        AssemblyType.TRYTE,
        (),
        ((0, AssemblyType.TRYTE), (1, AssemblyType.REFERENCE), (2, AssemblyType.TRYTE)),
        (AssemblyBlock("entry", (
            AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=1),
            AssemblyInstruction(
                AssemblyOpcode.TADDR,
                (1, 0),
                reference_target=AssemblyType.TRYTE,
                reference_mutable=True,
            ),
            AssemblyInstruction(AssemblyOpcode.TCONST, (2,), immediate=7),
            AssemblyInstruction(
                AssemblyOpcode.TREFSTORE,
                (1, 2),
                reference_target=AssemblyType.TRYTE,
                reference_mutable=True,
            ),
            AssemblyInstruction(AssemblyOpcode.TRET, (2,)),
        )),),
        reference_targets=((1, AssemblyType.TRYTE, True),),
    )
    return AssemblyProgram((function,))


def test_address_taken_referent_is_stack_resident_before_coloring() -> None:
    plan = analyze_allocation(_reference_program().functions[0])
    assert plan.address_taken == frozenset({0})
    assert plan.is_stack_resident(0)
    assert 1 not in plan.address_taken


def test_native_reference_ops_use_canonical_frame_storage_and_reserved_scratch() -> None:
    native = X8664Emitter(
        _reference_program(),
        max_frames=64,
        max_instructions=1000,
        register_allocation=True,
    ).emit()
    assert "lea r10, [rbp" in native
    assert "mov qword ptr [r10], r11" in native
    assert "r10" not in {"rbx", "r12", "r13", "r14", "r15", "rdi", "rsi", "rdx", "rcx", "r8", "r9"}


def test_reference_parameter_reuses_existing_one_word_call_abi() -> None:
    source = (
        "fn modify(ref: &mut tryte) -> tryte:\n"
        "    *ref = 10\n"
        "    return *ref\n"
        "fn main() -> tryte:\n"
        "    mut value: tryte = 1\n"
        "    result: tryte = modify(&mut value)\n"
        "    return value\n"
    )
    program = compile_source(source).assembly
    callee = next(function for function in program.functions if function.name == "modify")
    caller = next(function for function in program.functions if function.name == "main")
    assert callee.parameters[0].type is AssemblyType.REFERENCE
    assert callee.parameters[0].reference_target is AssemblyType.TRYTE
    calls = [item for item in caller.instructions if item.opcode is AssemblyOpcode.TCALL]
    assert len(calls) == 1
    assert len(calls[0].argument_registers) == 1


@pytest.mark.parametrize("optimization", ["O0", "O1"])
@pytest.mark.parametrize("register_allocation", [False, True])
def test_native_direct_and_indirect_coherence_matrix(
    optimization: str,
    register_allocation: bool,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    write_through = (
        "fn main() -> tryte:\n"
        "    mut value: tryte = 1\n"
        "    ref: &mut tryte = &mut value\n"
        "    *ref = 7\n"
        "    return value\n"
    )
    direct_through = (
        "fn main() -> tryte:\n"
        "    mut value: tryte = 1\n"
        "    ref: &mut tryte = &mut value\n"
        "    value = 9\n"
        "    return *ref\n"
    )
    assert _run_native(write_through, optimization, register_allocation, native_toolchain, tmp_path / "write") == 7
    assert _run_native(direct_through, optimization, register_allocation, native_toolchain, tmp_path / "direct") == 9


@pytest.mark.parametrize("optimization", ["O0", "O1"])
@pytest.mark.parametrize("register_allocation", [False, True])
def test_native_callee_mutation_is_visible_to_caller(
    optimization: str,
    register_allocation: bool,
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    source = (
        "fn modify(ref: &mut tryte) -> tryte:\n"
        "    *ref = 10\n"
        "    return *ref\n"
        "fn main() -> tryte:\n"
        "    mut value: tryte = 1\n"
        "    result: tryte = modify(&mut value)\n"
        "    return value\n"
    )
    assert _run_native(source, optimization, register_allocation, native_toolchain, tmp_path) == 10
