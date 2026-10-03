from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3 import assembly_program_text_adapter
from bootstrap.s3.assembly import AssemblyProgram, parse_assembly
from bootstrap.s3.assembly_program_text_adapter import render_supported_program
from bootstrap.s3.static_text import StaticTextDocument


REPO_ROOT = Path(__file__).resolve().parents[1]
INSPECT_ASSEMBLY_GOLDENS = tuple(
    sorted((REPO_ROOT / "tests" / "golden" / "inspect").glob("*.assembly.txt"))
)


def _read_lf_normalized_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_assembly_program_render_delegates_to_supported_program(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    program = AssemblyProgram(())
    calls: list[AssemblyProgram] = []

    def spy(candidate: AssemblyProgram) -> StaticTextDocument:
        calls.append(candidate)
        return StaticTextDocument("delegated\n")

    monkeypatch.setattr(
        assembly_program_text_adapter,
        "render_supported_program",
        spy,
    )

    assert program.render() == "delegated\n"
    assert calls == [program]


def test_assembly_program_render_matches_supported_path_for_inspect_goldens() -> None:
    assert INSPECT_ASSEMBLY_GOLDENS

    for golden in INSPECT_ASSEMBLY_GOLDENS:
        expected = _read_lf_normalized_text(golden)
        program = parse_assembly(expected)

        assert program.render() == expected
        assert program.render() == render_supported_program(program).text
        assert "\r\n" not in program.render()
        assert program.render().endswith("\n")


def test_assembly_program_render_preserves_empty_program_output() -> None:
    assert AssemblyProgram(()).render() == ".s3asm 0.7.0\n\n\n"
