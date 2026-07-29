from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from bootstrap.s3 import assembly_program_text_adapter, assembly_text_probe
from bootstrap.s3.assembly_text_renderer import (
    AssemblyTextRenderer,
    AssemblyTextSource,
)
from bootstrap.s3.static_text import StaticTextDocument


REPO_ROOT = Path(__file__).resolve().parents[1]
FIRST_ASSEMBLY_GOLDEN = (
    REPO_ROOT / "tests" / "golden" / "inspect" / "first.assembly.txt"
)
SIMPLE_CALL_ASSEMBLY_GOLDEN = (
    REPO_ROOT / "tests" / "golden" / "inspect" / "simple_call.assembly.txt"
)
SIGN_ASSEMBLY_GOLDEN = (
    REPO_ROOT / "tests" / "golden" / "inspect" / "sign.assembly.txt"
)
ACTUAL_OUTPUT_ROOT = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_actual"
)
FIRST_ACTUAL_OUTPUT = ACTUAL_OUTPUT_ROOT / "first.assembly.txt"
SIMPLE_CALL_ACTUAL_OUTPUT = ACTUAL_OUTPUT_ROOT / "simple_call.assembly.txt"
SIGN_ACTUAL_OUTPUT = ACTUAL_OUTPUT_ROOT / "sign.assembly.txt"


def _read_lf_normalized_golden_bytes(path: Path) -> bytes:
    return path.read_text(encoding="utf-8").encode("utf-8")


def _run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_renderer_core_returns_static_text_document_with_lf() -> None:
    document = (
        AssemblyTextRenderer()
        .emit_header()
        .emit_function("main", "tryte")
        .emit_register(0, "tryte")
        .emit_label("entry")
        .emit_instruction("TRET", "r0", source=AssemblyTextSource(1, 1, 0))
        .emit_end()
        .build()
    )

    assert isinstance(document, StaticTextDocument)
    assert document.text == (
        ".s3asm 0.5.0\n"
        "\n"
        ".function main -> tryte\n"
        "    .register r0, tryte\n"
        ".label entry\n"
        "    TRET   r0 ; source=1:1:0\n"
        ".end\n"
    )
    assert document.utf8_bytes == document.text.encode("utf-8")
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes
    assert document.text.endswith("\n")


def test_renderer_core_emits_memory_declaration() -> None:
    document = (
        AssemblyTextRenderer()
        .emit_header()
        .emit_function("main", "tryte")
        .emit_memory(0, "tryte", 2, True)
        .emit_label("entry")
        .emit_instruction("TRET", "r0")
        .emit_end()
        .build()
    )

    assert document.text == (
        ".s3asm 0.5.0\n"
        "\n"
        ".function main -> tryte\n"
        "    .memory m0, tryte, 2, mutable\n"
        ".label entry\n"
        "    TRET   r0\n"
        ".end\n"
    )
    assert "\r\n" not in document.text
    assert document.text.endswith("\n")


def test_first_fixture_probe_delegates_to_renderer_core(monkeypatch) -> None:
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

    document = assembly_text_probe.build_first_fixture_assembly_text()

    assert calls == ["init", "build"]
    assert document.utf8_bytes == _read_lf_normalized_golden_bytes(
        FIRST_ASSEMBLY_GOLDEN
    )


def test_simple_call_fixture_probe_delegates_to_renderer_core(monkeypatch) -> None:
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

    document = assembly_text_probe.build_simple_call_fixture_assembly_text()

    assert calls == ["init", "build"]
    assert document.utf8_bytes == _read_lf_normalized_golden_bytes(
        SIMPLE_CALL_ASSEMBLY_GOLDEN
    )


def test_sign_fixture_probe_delegates_to_renderer_core(monkeypatch) -> None:
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

    document = assembly_text_probe.build_sign_fixture_assembly_text()

    assert calls == ["init", "build"]
    assert document.utf8_bytes == _read_lf_normalized_golden_bytes(
        SIGN_ASSEMBLY_GOLDEN
    )


def test_renderer_core_builds_first_fixture_against_inspect_golden() -> None:
    document = assembly_text_probe.build_first_fixture_assembly_text()
    expected = _read_lf_normalized_golden_bytes(FIRST_ASSEMBLY_GOLDEN)

    assert isinstance(document, StaticTextDocument)
    assert document.utf8_bytes == expected
    assert document.byte_count == 377
    assert document.line_count == 16
    assert (
        document.sha256
        == "a144d584ed40287d10cff5ecc50a170823aac7ddd0a7fed455837b936131a90f"
    )
    assert document.sha256 == hashlib.sha256(expected).hexdigest()
    assert b"\r\n" not in document.utf8_bytes


def test_renderer_core_builds_simple_call_fixture_against_inspect_golden() -> None:
    document = assembly_text_probe.build_simple_call_fixture_assembly_text()
    expected = _read_lf_normalized_golden_bytes(SIMPLE_CALL_ASSEMBLY_GOLDEN)

    assert isinstance(document, StaticTextDocument)
    assert document.utf8_bytes == expected
    assert document.byte_count == 448
    assert document.line_count == 21
    assert (
        document.sha256
        == "d6de00c8c50618bcc8f3a458267eb8590956a9451980084b1add2f59d3267c0f"
    )
    assert document.sha256 == hashlib.sha256(expected).hexdigest()
    assert document.text.endswith("\n")
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes


def test_renderer_core_builds_sign_fixture_against_inspect_golden() -> None:
    document = assembly_text_probe.build_sign_fixture_assembly_text()
    expected = _read_lf_normalized_golden_bytes(SIGN_ASSEMBLY_GOLDEN)

    assert isinstance(document, StaticTextDocument)
    assert document.utf8_bytes == expected
    assert document.byte_count == 829
    assert document.line_count == 32
    assert (
        document.sha256
        == "2002bbcdf4f893efafb34d3e194dd6b5602eb2d023a2d0d064a5d2642d48f880"
    )
    assert document.sha256 == hashlib.sha256(expected).hexdigest()
    assert document.text.endswith("\n")
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes


def test_renderer_core_builds_first_fixture_against_candidate_actual_output() -> None:
    document = assembly_text_probe.build_first_fixture_assembly_text()
    actual = FIRST_ACTUAL_OUTPUT.read_bytes()

    assert actual == document.utf8_bytes
    assert len(actual) == 377
    assert hashlib.sha256(actual).hexdigest() == document.sha256
    assert b"\r\n" not in actual
    assert actual.endswith(b"\n")


def test_renderer_core_builds_simple_call_fixture_against_candidate_actual_output() -> None:
    document = assembly_text_probe.build_simple_call_fixture_assembly_text()
    actual = SIMPLE_CALL_ACTUAL_OUTPUT.read_bytes()

    assert actual == document.utf8_bytes
    assert len(actual) == 448
    assert hashlib.sha256(actual).hexdigest() == document.sha256
    assert b"\r\n" not in actual
    assert actual.endswith(b"\n")


def test_renderer_core_builds_sign_fixture_against_candidate_actual_output() -> None:
    document = assembly_text_probe.build_sign_fixture_assembly_text()
    actual = SIGN_ACTUAL_OUTPUT.read_bytes()

    assert actual == document.utf8_bytes
    assert len(actual) == 829
    assert hashlib.sha256(actual).hexdigest() == document.sha256
    assert b"\r\n" not in actual
    assert actual.endswith(b"\n")


def test_candidate_actual_outputs_remain_unchanged() -> None:
    expected = {
        FIRST_ACTUAL_OUTPUT: (
            "a144d584ed40287d10cff5ecc50a170823aac7ddd0a7fed455837b936131a90f",
            377,
            16,
        ),
        SIMPLE_CALL_ACTUAL_OUTPUT: (
            "d6de00c8c50618bcc8f3a458267eb8590956a9451980084b1add2f59d3267c0f",
            448,
            21,
        ),
        SIGN_ACTUAL_OUTPUT: (
            "2002bbcdf4f893efafb34d3e194dd6b5602eb2d023a2d0d064a5d2642d48f880",
            829,
            32,
        ),
    }

    for path, (sha256, byte_count, line_count) in expected.items():
        data = path.read_bytes()

        assert path.is_file()
        assert hashlib.sha256(data).hexdigest() == sha256
        assert len(data) == byte_count
        assert len(data.decode("utf-8").splitlines()) == line_count
        assert b"\r\n" not in data
        assert data.endswith(b"\n")


def test_candidate_compare_available_still_passes() -> None:
    completed = _run_tool(
        "tools/compare_assembly_renderer.py",
        "--candidate-compare-available",
    )

    assert completed.returncode == 0
    assert "first expected=tests/golden/inspect/first.assembly.txt" in completed.stdout
    assert (
        "simple_call expected=tests/golden/inspect/simple_call.assembly.txt"
        in completed.stdout
    )
    assert "sign expected=tests/golden/inspect/sign.assembly.txt" in completed.stdout
    assert "available comparisons: 3" in completed.stdout
    assert "passed comparisons: 3" in completed.stdout


def test_compare_check_now_passes() -> None:
    completed = _run_tool("tools/compare_assembly_renderer.py", "--check")

    assert completed.returncode == 0
    assert "S3 Assembly renderer comparison check: ok" in completed.stdout
    assert "actual outputs: passed" in completed.stdout
    assert "available comparisons: passed" in completed.stdout
    assert "renderer implementation: complete" in completed.stdout
    assert "full text rendering: passed" in completed.stdout
    assert "global check: passed" in completed.stdout
