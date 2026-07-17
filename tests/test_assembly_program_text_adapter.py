from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from bootstrap.s3 import assembly_program_text_adapter
from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
)
from bootstrap.s3.assembly_program_text_adapter import (
    AssemblyProgramTextAdapter,
    AssemblyProgramTextAdapterError,
    render_first_program,
)
from bootstrap.s3.assembly_text_renderer import AssemblyTextRenderer
from bootstrap.s3.diagnostics import SourceLocation
from bootstrap.s3.static_text import StaticTextDocument


REPO_ROOT = Path(__file__).resolve().parents[1]
FIRST_ASSEMBLY_GOLDEN = (
    REPO_ROOT / "tests" / "golden" / "inspect" / "first.assembly.txt"
)
FIRST_ACTUAL_OUTPUT = (
    REPO_ROOT
    / "tests"
    / "golden"
    / "assembly_renderer_candidate_actual"
    / "first.assembly.txt"
)


def _read_lf_normalized_golden_bytes(path: Path) -> bytes:
    return path.read_text(encoding="utf-8").encode("utf-8")


def _first_program() -> AssemblyProgram:
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


def test_render_first_program_matches_lf_normalized_inspect_golden() -> None:
    document = render_first_program(_first_program())
    expected = _read_lf_normalized_golden_bytes(FIRST_ASSEMBLY_GOLDEN)

    assert isinstance(document, StaticTextDocument)
    assert document.utf8_bytes == expected
    assert document.byte_count == 441
    assert document.line_count == 18
    assert (
        document.sha256
        == "46ebd2aef715d7a7e9f7ada01ca844b8ae23494ff6a5333f78c75db2eaca2f67"
    )
    assert document.sha256 == hashlib.sha256(expected).hexdigest()
    assert document.text.endswith("\n")
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes


def test_render_first_program_matches_candidate_actual_output() -> None:
    document = AssemblyProgramTextAdapter().render_first_program(_first_program())
    actual = FIRST_ACTUAL_OUTPUT.read_bytes()

    assert actual == document.utf8_bytes
    assert len(actual) == 441
    assert hashlib.sha256(actual).hexdigest() == document.sha256
    assert b"\r\n" not in actual
    assert actual.endswith(b"\n")


def test_render_first_program_uses_renderer_core(monkeypatch) -> None:
    calls: list[str] = []

    class SpyRenderer(AssemblyTextRenderer):
        def __init__(self) -> None:
            calls.append("init")
            super().__init__()

        def build(self) -> StaticTextDocument:
            calls.append("build")
            return super().build()

    monkeypatch.setattr(
        assembly_program_text_adapter,
        "AssemblyTextRenderer",
        SpyRenderer,
    )

    document = render_first_program(_first_program())

    assert calls == ["init", "build"]
    assert document.utf8_bytes == _read_lf_normalized_golden_bytes(
        FIRST_ASSEMBLY_GOLDEN
    )


def test_render_first_program_rejects_non_first_subset() -> None:
    program = AssemblyProgram(
        (
            AssemblyFunction(
                "add",
                AssemblyType.TRYTE,
                (),
                (),
                (),
            ),
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                (),
                (),
            ),
        )
    )

    with pytest.raises(
        AssemblyProgramTextAdapterError,
        match="first adapter expects exactly one function",
    ):
        render_first_program(program)
