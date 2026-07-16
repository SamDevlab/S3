"""In-memory probes for deterministic Assembly text output."""

from __future__ import annotations

from bootstrap.s3.static_text import StaticTextDocument, StaticTextLineEmitter


def build_first_fixture_assembly_text() -> StaticTextDocument:
    """Build the expected Assembly text for ``examples/first.s3`` in memory."""

    emitter = StaticTextLineEmitter()
    emitter.emit_line(".s3asm 0.5.0")
    emitter.emit_blank_line()
    emitter.emit_line(".function main -> tryte")
    emitter.emit_line(".register r0, tryte", indent=1)
    emitter.emit_line(".register r1, tryte", indent=1)
    emitter.emit_line(".register r2, tryte", indent=1)
    emitter.emit_line(".register r3, tryte", indent=1)
    emitter.emit_line(".register r4, tryte", indent=1)
    emitter.emit_line(".register r5, tryte", indent=1)
    emitter.emit_line(".label entry")
    emitter.emit_line("TCONST r0, 10 ; source=2:16:35", indent=1)
    emitter.emit_line("TMOV   r1, r0 ; source=2:5:24", indent=1)
    emitter.emit_line("TCONST r2, 4 ; source=3:16:53", indent=1)
    emitter.emit_line("TMOV   r3, r2 ; source=3:5:42", indent=1)
    emitter.emit_line("TINV   r4, r3 ; source=4:14:68", indent=1)
    emitter.emit_line("TADD   r5, r1, r4 ; source=4:14:68", indent=1)
    emitter.emit_line("TRET   r5 ; source=4:5:59", indent=1)
    emitter.emit_line(".end")
    return emitter.build()
