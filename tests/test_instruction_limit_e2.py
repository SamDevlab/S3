"""Tests for native instruction limit instrumentation (Milestone 0.7 E2)."""

import pytest

from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
)
from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    X8664Backend,
    generate_native_assembly,
)
from bootstrap.s3.cli import main


def test_cli_rejects_negative_native_limit(capsys):
    code = main(["native-asm", "--max-instructions", "-5", "dummy.s3"])
    assert code == 2
    captured = capsys.readouterr()
    assert "error: --max-instructions must be at least 1" in captured.err


def test_cli_rejects_zero_native_limit(capsys):
    code = main(["run-native", "--max-instructions", "0", "dummy.s3"])
    assert code == 2
    captured = capsys.readouterr()
    assert "error: --max-instructions must be at least 1" in captured.err


def test_backend_validates_type():
    program = AssemblyProgram([AssemblyFunction("main", AssemblyType.TRYTE, (), (), [AssemblyBlock("entry", [])])])
    with pytest.raises(TypeError) as exception:
        generate_native_assembly(program, max_instructions=True)
    assert "must be an integer" in str(exception.value)


def test_backend_validates_value():
    program = AssemblyProgram([AssemblyFunction("main", AssemblyType.TRYTE, (), (), [AssemblyBlock("entry", [])])])
    with pytest.raises(NativeBackendError) as exception:
        generate_native_assembly(program, max_instructions=0)
    assert "must be at least 1" in str(exception.value)


def test_instrumentation_structural_elements():
    program = AssemblyProgram(
        [
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE)),
                [
                    AssemblyBlock(
                        "entry",
                        [
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                [0],
                                immediate=42,
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                [0],
                            ),
                        ],
                    )
                ],
            )
        ]
    )
    asm = generate_native_assembly(program, max_instructions=100000)

    # The eligible PER path stores the shared remaining budget in data.
    assert "__s3_instruction_remaining:\n    .quad 100000" in asm
    assert "__s3_frame_count" in asm
    assert "__s3_instruction_count" in asm

    # Each of the two logical instructions is charged before execution.
    assert asm.count("\n    dec r15\n") == 2
    assert asm.count("    inc qword ptr [rip + __s3_instruction_count]") == 0

    # The non-RA compatibility path keeps its memory counter.
    stack_asm = X8664Backend(
        max_instructions=100000,
        register_allocation=False,
    ).generate(program)
    assert stack_asm.count("inc qword ptr [rip + __s3_instruction_count]") == 2


def test_instrumentation_64_bit_limit():
    program = AssemblyProgram(
        [
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE)),
                [
                    AssemblyBlock(
                        "entry",
                        [
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                [0],
                                immediate=42,
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                [0],
                            ),
                        ],
                    )
                ],
            )
        ]
    )
    limit = 5000000000  # greater than 2**31 - 1, still representable by r15
    asm = generate_native_assembly(program, max_instructions=limit)

    assert f"    .quad {limit}" in asm
    assert asm.count("\n    dec r15\n") == 2
    assert f"movabs r11, {limit}" not in asm


def test_instrumentation_above_signed_64_bit_limit_uses_memory_counter():
    program = AssemblyProgram(
        [
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE)),
                [
                    AssemblyBlock(
                        "entry",
                        [
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                [0],
                                immediate=42,
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                [0],
                            ),
                        ],
                    )
                ],
            )
        ]
    )
    limit = (1 << 63) + 17
    asm = X8664Backend(max_instructions=limit).generate(program)

    instrumentation = (
        f"    movabs r11, {limit}\n"
        "    cmp qword ptr [rip + __s3_instruction_count], r11\n"
        "    jae .L__s3_failure_site_1\n"
        "    inc qword ptr [rip + __s3_instruction_count]\n"
    )
    assert instrumentation in asm


def test_instrumentation_context():
    program = AssemblyProgram(
        [
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE)),
                [
                    AssemblyBlock(
                        "entry",
                        [
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                [0],
                                immediate=42,
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TJMP,
                                [],
                                labels=("next",),
                            ),
                        ],
                    ),
                    AssemblyBlock(
                        "next",
                        [
                            AssemblyInstruction(
                                AssemblyOpcode.TMOV,
                                [1, 0],
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                [1],
                            ),
                        ],
                    ),
                ],
            )
        ]
    )
    asm = generate_native_assembly(program, max_instructions=1000)

    # Context for TCONST
    assert "instruction limit 1000 exceeded" in asm
    # It generates 4 separate failure sites for the 4 opcodes
    assert asm.count("instruction limit 1000 exceeded") == 4
    assert "at source unknown (block entry, TCONST)" in asm
    assert "at source unknown (block next, TMOV)" in asm


def test_instrumentation_deterministic_change():
    program = AssemblyProgram(
        [
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE)),
                [
                    AssemblyBlock(
                        "entry",
                        [
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                [0],
                                immediate=42,
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                [0],
                            ),
                        ],
                    )
                ],
            )
        ]
    )
    asm1 = generate_native_assembly(program, max_instructions=100)
    asm2 = generate_native_assembly(program, max_instructions=200)

    # They should differ only by the instruction limit occurrences
    diff1 = asm1.replace("100", "XXX")
    diff2 = asm2.replace("200", "XXX")
    assert diff1 == diff2
