from __future__ import annotations

from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
)
from tools.scientific_budget_benchmark import _assembly_program_sha256


def _program_with_tmul(destination: int) -> AssemblyProgram:
    return AssemblyProgram(
        functions=(
            AssemblyFunction(
                name="main",
                return_type=AssemblyType.F64,
                parameters=(),
                register_types=(
                    (0, AssemblyType.F64),
                    (1, AssemblyType.F64),
                    (destination, AssemblyType.F64),
                ),
                blocks=(
                    AssemblyBlock(
                        label="entry",
                        instructions=(
                            AssemblyInstruction(
                                opcode=AssemblyOpcode.TMUL,
                                registers=(destination, 0, 1),
                            ),
                            AssemblyInstruction(
                                opcode=AssemblyOpcode.TRET,
                                registers=(destination,),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def test_assembly_program_fingerprint_handles_opcodes_outside_text_adapter() -> None:
    program = _program_with_tmul(2)

    first = _assembly_program_sha256(program)
    second = _assembly_program_sha256(program)

    assert len(first) == 64
    assert first == second
    assert first != _assembly_program_sha256(_program_with_tmul(3))
