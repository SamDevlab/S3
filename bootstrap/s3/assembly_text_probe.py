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
    render_simple_call_program,
)
from bootstrap.s3.assembly_text_renderer import (
    AssemblyTextRenderer,
    AssemblyTextSource,
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

    renderer = AssemblyTextRenderer()
    renderer.emit_header()
    renderer.emit_function("sign", "trit")
    renderer.emit_param(0, "tryte")
    renderer.emit_register(1, "tryte")
    renderer.emit_register(2, "trit")
    renderer.emit_register(3, "trit")
    renderer.emit_register(4, "trit")
    renderer.emit_register(5, "trit")
    renderer.emit_register(6, "trit")
    renderer.emit_label("entry")
    renderer.emit_instruction(
        "TCONST",
        "r1",
        0,
        source=AssemblyTextSource(2, 21, 51),
    )
    renderer.emit_instruction(
        "TCMP",
        "r2",
        "r0",
        "r1",
        source=AssemblyTextSource(2, 17, 47),
    )
    renderer.emit_instruction(
        "TBR3",
        "r2",
        "switch_negative_0",
        "switch_neutral_1",
        "switch_positive_2",
        source=AssemblyTextSource(2, 5, 35),
    )
    renderer.emit_label("switch_negative_0")
    renderer.emit_instruction(
        "TCONST",
        "r3",
        1,
        source=AssemblyTextSource(4, 21, 86),
    )
    renderer.emit_instruction(
        "TINV",
        "r4",
        "r3",
        source=AssemblyTextSource(4, 20, 85),
    )
    renderer.emit_instruction("TRET", "r4", source=AssemblyTextSource(4, 13, 78))
    renderer.emit_label("switch_neutral_1")
    renderer.emit_instruction(
        "TCONST",
        "r5",
        0,
        source=AssemblyTextSource(7, 20, 119),
    )
    renderer.emit_instruction("TRET", "r5", source=AssemblyTextSource(7, 13, 112))
    renderer.emit_label("switch_positive_2")
    renderer.emit_instruction(
        "TCONST",
        "r6",
        1,
        source=AssemblyTextSource(10, 20, 152),
    )
    renderer.emit_instruction("TRET", "r6", source=AssemblyTextSource(10, 13, 145))
    renderer.emit_end()
    renderer.emit_blank_line()
    renderer.emit_function("main", "trit")
    renderer.emit_register(0, "tryte")
    renderer.emit_register(1, "tryte")
    renderer.emit_register(2, "trit")
    renderer.emit_label("entry")
    renderer.emit_instruction(
        "TCONST",
        "r0",
        20,
        source=AssemblyTextSource(13, 18, 191),
    )
    renderer.emit_instruction(
        "TINV",
        "r1",
        "r0",
        source=AssemblyTextSource(13, 17, 190),
    )
    renderer.emit_instruction(
        "TCALL",
        "r2",
        "sign",
        "r1",
        source=AssemblyTextSource(13, 12, 185),
    )
    renderer.emit_instruction("TRET", "r2", source=AssemblyTextSource(13, 5, 178))
    renderer.emit_end()
    return renderer.build()
