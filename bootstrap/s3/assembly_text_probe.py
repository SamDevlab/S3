"""In-memory probes for deterministic Assembly text output."""

from __future__ import annotations

from bootstrap.s3.assembly_text_renderer import (
    AssemblyTextRenderer,
    AssemblyTextSource,
)
from bootstrap.s3.static_text import StaticTextDocument, StaticTextLineEmitter


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

    emitter = StaticTextLineEmitter()
    emitter.emit_line(".s3asm 0.5.0")
    emitter.emit_blank_line()
    emitter.emit_line(".function sign -> trit")
    emitter.emit_line(".param r0, tryte", indent=1)
    emitter.emit_line(".register r1, tryte", indent=1)
    emitter.emit_line(".register r2, trit", indent=1)
    emitter.emit_line(".register r3, trit", indent=1)
    emitter.emit_line(".register r4, trit", indent=1)
    emitter.emit_line(".register r5, trit", indent=1)
    emitter.emit_line(".register r6, trit", indent=1)
    emitter.emit_line(".label entry")
    emitter.emit_line("TCONST r1, 0 ; source=2:21:51", indent=1)
    emitter.emit_line("TCMP   r2, r0, r1 ; source=2:17:47", indent=1)
    emitter.emit_line(
        "TBR3   r2, switch_negative_0, switch_neutral_1, switch_positive_2 ; "
        "source=2:5:35",
        indent=1,
    )
    emitter.emit_line(".label switch_negative_0")
    emitter.emit_line("TCONST r3, 1 ; source=4:21:86", indent=1)
    emitter.emit_line("TINV   r4, r3 ; source=4:20:85", indent=1)
    emitter.emit_line("TRET   r4 ; source=4:13:78", indent=1)
    emitter.emit_line(".label switch_neutral_1")
    emitter.emit_line("TCONST r5, 0 ; source=7:20:119", indent=1)
    emitter.emit_line("TRET   r5 ; source=7:13:112", indent=1)
    emitter.emit_line(".label switch_positive_2")
    emitter.emit_line("TCONST r6, 1 ; source=10:20:152", indent=1)
    emitter.emit_line("TRET   r6 ; source=10:13:145", indent=1)
    emitter.emit_line(".end")
    emitter.emit_blank_line()
    emitter.emit_line(".function main -> trit")
    emitter.emit_line(".register r0, tryte", indent=1)
    emitter.emit_line(".register r1, tryte", indent=1)
    emitter.emit_line(".register r2, trit", indent=1)
    emitter.emit_line(".label entry")
    emitter.emit_line("TCONST r0, 20 ; source=13:18:191", indent=1)
    emitter.emit_line("TINV   r1, r0 ; source=13:17:190", indent=1)
    emitter.emit_line("TCALL  r2, sign, r1 ; source=13:12:185", indent=1)
    emitter.emit_line("TRET   r2 ; source=13:5:178", indent=1)
    emitter.emit_line(".end")
    return emitter.build()
