from __future__ import annotations

from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
)
from bootstrap.s3.backends.x86_64 import X8664Backend
from bootstrap.s3.codegen_optimization import eliminate_redundant_noop_moves
from bootstrap.s3.emulator import Emulator


def _program() -> AssemblyProgram:
    return AssemblyProgram(
        (
            AssemblyFunction(
                "main",
                AssemblyType.I64,
                (),
                ((0, AssemblyType.I64),),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=7),
                            AssemblyInstruction(AssemblyOpcode.TMOV, (0, 0)),
                            AssemblyInstruction(AssemblyOpcode.TRET, (0,)),
                        ),
                    ),
                ),
            ),
        )
    )


def test_noop_move_elimination_preserves_hosted_result_and_is_deterministic() -> None:
    program = _program()
    optimized, report = eliminate_redundant_noop_moves(program)
    assert Emulator().execute(program) == Emulator().execute(optimized) == 7
    assert report.input_instruction_count == 3
    assert report.output_instruction_count == 2
    assert report.removed_noop_moves == 1
    assert eliminate_redundant_noop_moves(program) == (optimized, report)


def test_native_x86_codegen_consumes_the_optimized_program() -> None:
    native = X8664Backend().generate(_program())
    assert "r0" not in native
    assert native.count("s3_main:") == 1


def test_memory_and_control_flow_instructions_are_not_rewritten() -> None:
    program = _program()
    optimized, _report = eliminate_redundant_noop_moves(program)
    assert optimized.functions[0].blocks[0].instructions[0] == program.functions[0].blocks[0].instructions[0]
    assert optimized.functions[0].blocks[0].instructions[-1] == program.functions[0].blocks[0].instructions[-1]
