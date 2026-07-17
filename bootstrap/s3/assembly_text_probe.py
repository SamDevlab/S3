"""In-memory probes for deterministic Assembly text output."""

from __future__ import annotations

from bootstrap.s3.assembly_text_renderer import (
    AssemblyTextRenderer,
    AssemblyTextSource,
)
from bootstrap.s3.static_text import StaticTextDocument


def build_first_fixture_assembly_text() -> StaticTextDocument:
    """Build the expected Assembly text for ``examples/first.s3`` in memory."""

    renderer = AssemblyTextRenderer()
    renderer.emit_header()
    renderer.emit_function("main", "tryte")
    renderer.emit_register(0, "tryte")
    renderer.emit_register(1, "tryte")
    renderer.emit_register(2, "tryte")
    renderer.emit_register(3, "tryte")
    renderer.emit_register(4, "tryte")
    renderer.emit_register(5, "tryte")
    renderer.emit_label("entry")
    renderer.emit_instruction(
        "TCONST",
        "r0",
        10,
        source=AssemblyTextSource(2, 16, 35),
    )
    renderer.emit_instruction(
        "TMOV",
        "r1",
        "r0",
        source=AssemblyTextSource(2, 5, 24),
    )
    renderer.emit_instruction(
        "TCONST",
        "r2",
        4,
        source=AssemblyTextSource(3, 16, 53),
    )
    renderer.emit_instruction(
        "TMOV",
        "r3",
        "r2",
        source=AssemblyTextSource(3, 5, 42),
    )
    renderer.emit_instruction(
        "TINV",
        "r4",
        "r3",
        source=AssemblyTextSource(4, 14, 68),
    )
    renderer.emit_instruction(
        "TADD",
        "r5",
        "r1",
        "r4",
        source=AssemblyTextSource(4, 14, 68),
    )
    renderer.emit_instruction("TRET", "r5", source=AssemblyTextSource(4, 5, 59))
    renderer.emit_end()
    return renderer.build()


def build_simple_call_fixture_assembly_text() -> StaticTextDocument:
    """Build the expected Assembly text for ``examples/simple_call.s3`` in memory."""

    renderer = AssemblyTextRenderer()
    renderer.emit_header()
    renderer.emit_function("add", "tryte")
    renderer.emit_param(0, "tryte")
    renderer.emit_param(1, "tryte")
    renderer.emit_register(2, "tryte")
    renderer.emit_label("entry")
    renderer.emit_instruction(
        "TADD",
        "r2",
        "r0",
        "r1",
        source=AssemblyTextSource(2, 14, 50),
    )
    renderer.emit_instruction("TRET", "r2", source=AssemblyTextSource(2, 5, 41))
    renderer.emit_end()
    renderer.emit_blank_line()
    renderer.emit_function("main", "tryte")
    renderer.emit_register(0, "tryte")
    renderer.emit_register(1, "tryte")
    renderer.emit_register(2, "tryte")
    renderer.emit_label("entry")
    renderer.emit_instruction(
        "TCONST",
        "r0",
        10,
        source=AssemblyTextSource(5, 16, 90),
    )
    renderer.emit_instruction(
        "TCONST",
        "r1",
        5,
        source=AssemblyTextSource(5, 20, 94),
    )
    renderer.emit_instruction(
        "TCALL",
        "r2",
        "add",
        "r0",
        "r1",
        source=AssemblyTextSource(5, 12, 86),
    )
    renderer.emit_instruction("TRET", "r2", source=AssemblyTextSource(5, 5, 79))
    renderer.emit_end()
    return renderer.build()


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
