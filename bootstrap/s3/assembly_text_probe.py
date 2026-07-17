"""In-memory probes for deterministic Assembly text output."""

from __future__ import annotations

from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyParameter,
    AssemblyProgram,
    AssemblyType,
)
from bootstrap.s3.assembly_program_text_adapter import (
    render_first_program,
    render_sign_program,
    render_simple_call_program,
)
from bootstrap.s3.diagnostics import SourceLocation
from bootstrap.s3.static_text import StaticTextDocument


def build_first_fixture_assembly_text() -> StaticTextDocument:
    """Build the expected Assembly text for ``examples/first.s3`` in memory."""

    return render_first_program(_build_first_fixture_assembly_program())


def _build_first_fixture_assembly_program() -> AssemblyProgram:
    return AssemblyProgram(
        (
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                tuple((register, AssemblyType.TRYTE) for register in range(6)),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (0,),
                                immediate=10,
                                source=SourceLocation(35, 2, 16),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TMOV,
                                (1, 0),
                                source=SourceLocation(24, 2, 5),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (2,),
                                immediate=4,
                                source=SourceLocation(53, 3, 16),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TMOV,
                                (3, 2),
                                source=SourceLocation(42, 3, 5),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TINV,
                                (4, 3),
                                source=SourceLocation(68, 4, 14),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TADD,
                                (5, 1, 4),
                                source=SourceLocation(68, 4, 14),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (5,),
                                source=SourceLocation(59, 4, 5),
                            ),
                        ),
                    ),
                ),
            ),
        )
    )


def build_simple_call_fixture_assembly_text() -> StaticTextDocument:
    """Build the expected Assembly text for ``examples/simple_call.s3`` in memory."""

    return render_simple_call_program(_build_simple_call_fixture_assembly_program())


def _build_simple_call_fixture_assembly_program() -> AssemblyProgram:
    return AssemblyProgram(
        (
            AssemblyFunction(
                "add",
                AssemblyType.TRYTE,
                (
                    AssemblyParameter(0, AssemblyType.TRYTE),
                    AssemblyParameter(1, AssemblyType.TRYTE),
                ),
                ((2, AssemblyType.TRYTE),),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TADD,
                                (2, 0, 1),
                                source=SourceLocation(50, 2, 14),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (2,),
                                source=SourceLocation(41, 2, 5),
                            ),
                        ),
                    ),
                ),
            ),
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                tuple((register, AssemblyType.TRYTE) for register in range(3)),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (0,),
                                immediate=10,
                                source=SourceLocation(90, 5, 16),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (1,),
                                immediate=5,
                                source=SourceLocation(94, 5, 20),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TCALL,
                                (2, 0, 1),
                                callee="add",
                                source=SourceLocation(86, 5, 12),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (2,),
                                source=SourceLocation(79, 5, 5),
                            ),
                        ),
                    ),
                ),
            ),
        )
    )


def build_sign_fixture_assembly_text() -> StaticTextDocument:
    """Build the expected Assembly text for ``examples/sign.s3`` in memory."""

    return render_sign_program(_build_sign_fixture_assembly_program())


def _build_sign_fixture_assembly_program() -> AssemblyProgram:
    return AssemblyProgram(
        (
            AssemblyFunction(
                "sign",
                AssemblyType.TRIT,
                (AssemblyParameter(0, AssemblyType.TRYTE),),
                (
                    (1, AssemblyType.TRYTE),
                    (2, AssemblyType.TRIT),
                    (3, AssemblyType.TRIT),
                    (4, AssemblyType.TRIT),
                    (5, AssemblyType.TRIT),
                    (6, AssemblyType.TRIT),
                ),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (1,),
                                immediate=0,
                                source=SourceLocation(51, 2, 21),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TCMP,
                                (2, 0, 1),
                                source=SourceLocation(47, 2, 17),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TBR3,
                                (2,),
                                labels=(
                                    "switch_negative_0",
                                    "switch_neutral_1",
                                    "switch_positive_2",
                                ),
                                source=SourceLocation(35, 2, 5),
                            ),
                        ),
                    ),
                    AssemblyBlock(
                        "switch_negative_0",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (3,),
                                immediate=1,
                                source=SourceLocation(86, 4, 21),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TINV,
                                (4, 3),
                                source=SourceLocation(85, 4, 20),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (4,),
                                source=SourceLocation(78, 4, 13),
                            ),
                        ),
                    ),
                    AssemblyBlock(
                        "switch_neutral_1",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (5,),
                                immediate=0,
                                source=SourceLocation(119, 7, 20),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (5,),
                                source=SourceLocation(112, 7, 13),
                            ),
                        ),
                    ),
                    AssemblyBlock(
                        "switch_positive_2",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (6,),
                                immediate=1,
                                source=SourceLocation(152, 10, 20),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (6,),
                                source=SourceLocation(145, 10, 13),
                            ),
                        ),
                    ),
                ),
            ),
            AssemblyFunction(
                "main",
                AssemblyType.TRIT,
                (),
                (
                    (0, AssemblyType.TRYTE),
                    (1, AssemblyType.TRYTE),
                    (2, AssemblyType.TRIT),
                ),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (0,),
                                immediate=20,
                                source=SourceLocation(191, 13, 18),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TINV,
                                (1, 0),
                                source=SourceLocation(190, 13, 17),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TCALL,
                                (2, 1),
                                callee="sign",
                                source=SourceLocation(185, 13, 12),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (2,),
                                source=SourceLocation(178, 13, 5),
                            ),
                        ),
                    ),
                ),
            ),
        )
    )
