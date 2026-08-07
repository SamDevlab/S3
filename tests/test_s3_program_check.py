from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import s3_program_check
from tools.s3_program_check import (
    S3Program,
    find_program,
    get_program_count,
    get_hosted_program_count,
    get_program_inventory,
    get_program_inventory_display,
    get_hosted_display,
    run_hosted_check,
)


def test_run_hosted_check_uses_provided_compilation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    program = S3Program(
        tmp_path / "hosted.s3",
        "hosted test",
        hosted_expected_return=7,
        max_instructions=321,
    )
    assembly = object()
    compilation = SimpleNamespace(assembly=assembly)
    calls: list[tuple[object, str, int]] = []

    def execute(
        actual_assembly: object,
        entry: str,
        *,
        max_instructions: int,
    ) -> int:
        calls.append((actual_assembly, entry, max_instructions))
        return 7

    monkeypatch.setattr(s3_program_check, "execute_assembly", execute)
    monkeypatch.setattr(
        s3_program_check,
        "run_source",
        lambda *_args, **_kwargs: pytest.fail("source must not be recompiled"),
    )

    assert run_hosted_check(program, compilation=compilation) == 7
    assert calls == [(assembly, "main", 321)]


def test_check_programs_reuses_compilation_for_hosted_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = s3_program_check.REPO_ROOT / "examples" / "first.s3"
    program = S3Program(path, "hosted test", hosted_expected_return=7)
    compilation = SimpleNamespace(assembly=object())
    received: list[object] = []

    monkeypatch.setattr(s3_program_check, "get_program_inventory", lambda: (program,))
    monkeypatch.setattr(s3_program_check, "compile_source", lambda _source: compilation)
    monkeypatch.setattr(s3_program_check, "_instruction_counts", lambda _result: (1, 1))

    def run(
        actual_program: S3Program,
        *,
        entry: str = "main",
        compilation: object | None = None,
    ) -> int:
        assert actual_program is program
        assert entry == "main"
        received.append(compilation)
        return 7

    monkeypatch.setattr(s3_program_check, "run_hosted_check", run)

    assert s3_program_check.check_programs() == 0
    assert received == [compilation]


def test_s3_program_check_inventory_exposes_renderer_stub_hosted_check() -> None:
    programs = get_program_inventory()
    stub = find_program("examples/self_hosting/assembly_renderer_stub.s3")
    bootstrap = find_program(
        "examples/self_hosting/assembly_renderer_bootstrap.s3"
    )
    output_model = find_program(
        "examples/self_hosting/assembly_renderer_output_model.s3"
    )
    text_segments = find_program(
        "examples/self_hosting/assembly_renderer_text_segments.s3"
    )
    line_blueprints = find_program(
        "examples/self_hosting/assembly_renderer_line_blueprints.s3"
    )
    line_sequences = find_program(
        "examples/self_hosting/assembly_renderer_line_sequences.s3"
    )
    line_encodings = find_program(
        "examples/self_hosting/assembly_renderer_line_encodings.s3"
    )
    event_stream = find_program(
        "examples/self_hosting/assembly_renderer_event_stream.s3"
    )
    event_writer = find_program(
        "examples/self_hosting/assembly_renderer_event_writer.s3"
    )
    output_buffer = find_program(
        "examples/self_hosting/assembly_renderer_output_buffer.s3"
    )
    pipeline = find_program(
        "examples/self_hosting/assembly_renderer_pipeline.s3"
    )
    text_builder = find_program(
        "examples/self_hosting/assembly_renderer_text_builder.s3"
    )
    text_fragments = find_program(
        "examples/self_hosting/assembly_renderer_text_fragments.s3"
    )
    fixed_tryte_buffer = find_program(
        "examples/self_hosting/fixed_tryte_buffer.s3"
    )

    assert len(programs) == get_program_count()
    assert stub is not None
    assert stub.hosted_expected_return == -1
    assert bootstrap is not None
    assert bootstrap.hosted_expected_return == 0
    assert output_model is not None
    assert output_model.hosted_expected_return == 0
    assert text_segments is not None
    assert text_segments.hosted_expected_return == 0
    assert line_blueprints is not None
    assert line_blueprints.hosted_expected_return == 0
    assert line_sequences is not None
    assert line_sequences.hosted_expected_return == 0
    assert line_encodings is not None
    assert line_encodings.hosted_expected_return == 0
    assert event_stream is not None
    assert event_stream.hosted_expected_return == 0
    assert event_writer is not None
    assert event_writer.hosted_expected_return == 0
    assert output_buffer is not None
    assert output_buffer.hosted_expected_return == 0
    assert pipeline is not None
    assert pipeline.hosted_expected_return == 0
    assert text_builder is not None
    assert text_builder.hosted_expected_return == 0
    assert text_fragments is not None
    assert text_fragments.hosted_expected_return == 0
    assert fixed_tryte_buffer is not None
    assert fixed_tryte_buffer.hosted_expected_return == 0


def test_s3_program_check_matches_registered_programs() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/s3_program_check.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert get_program_inventory_display() in completed.stdout
    assert get_hosted_display() in completed.stdout
    assert "examples/self_hosting/assembly_renderer_stub.s3" in completed.stdout
    assert "hosted expected return: -1" in completed.stdout
    assert "hosted actual return: -1" in completed.stdout
    assert "examples/self_hosting/assembly_renderer_bootstrap.s3" in completed.stdout
    assert "hosted expected return: 0" in completed.stdout
    assert "hosted actual return: 0" in completed.stdout
    assert "examples/self_hosting/assembly_renderer_output_model.s3" in completed.stdout
    assert "examples/self_hosting/assembly_renderer_text_segments.s3" in completed.stdout
    assert (
        "examples/self_hosting/assembly_renderer_line_blueprints.s3"
        in completed.stdout
    )
    assert (
        "examples/self_hosting/assembly_renderer_line_sequences.s3"
        in completed.stdout
    )
    assert (
        "examples/self_hosting/assembly_renderer_line_encodings.s3"
        in completed.stdout
    )
    assert (
        "examples/self_hosting/assembly_renderer_event_stream.s3"
        in completed.stdout
    )
    assert (
        "examples/self_hosting/assembly_renderer_event_writer.s3"
        in completed.stdout
    )
    assert (
        "examples/self_hosting/assembly_renderer_output_buffer.s3"
        in completed.stdout
    )
    assert "examples/self_hosting/assembly_renderer_pipeline.s3" in completed.stdout
    assert "examples/self_hosting/assembly_renderer_text_builder.s3" in completed.stdout
    assert "examples/self_hosting/assembly_renderer_text_fragments.s3" in completed.stdout
    assert completed.stderr == ""


def test_s3_program_check_lists_renderer_stub() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/s3_program_check.py", "list"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "examples/self_hosting/assembly_renderer_stub.s3" in completed.stdout
    assert "purpose: future Assembly renderer stub" in completed.stdout
    assert "expected: compiles" in completed.stdout
    assert "hosted expected return: -1" in completed.stdout
    assert "examples/self_hosting/assembly_renderer_bootstrap.s3" in completed.stdout
    assert "purpose: Assembly renderer bootstrap spike" in completed.stdout
    assert "hosted expected return: 0" in completed.stdout
    assert "examples/self_hosting/assembly_renderer_output_model.s3" in completed.stdout
    assert "purpose: Assembly renderer output model" in completed.stdout
    assert "examples/self_hosting/assembly_renderer_text_segments.s3" in completed.stdout
    assert "purpose: Assembly renderer text segment model" in completed.stdout
    assert (
        "examples/self_hosting/assembly_renderer_line_blueprints.s3"
        in completed.stdout
    )
    assert "purpose: Assembly renderer line blueprint model" in completed.stdout
    assert (
        "examples/self_hosting/assembly_renderer_line_sequences.s3"
        in completed.stdout
    )
    assert "purpose: Assembly renderer line sequence model" in completed.stdout
    assert (
        "examples/self_hosting/assembly_renderer_line_encodings.s3"
        in completed.stdout
    )
    assert (
        "purpose: Assembly renderer line content encoding model"
        in completed.stdout
    )
    assert (
        "examples/self_hosting/assembly_renderer_event_stream.s3"
        in completed.stdout
    )
    assert "purpose: Assembly renderer event stream model" in completed.stdout
    assert (
        "examples/self_hosting/assembly_renderer_event_writer.s3"
        in completed.stdout
    )
    assert (
        "purpose: Assembly renderer event writer state model"
        in completed.stdout
    )
    assert (
        "examples/self_hosting/assembly_renderer_output_buffer.s3"
        in completed.stdout
    )
    assert (
        "purpose: Assembly renderer hosted output buffer model"
        in completed.stdout
    )
    assert "examples/self_hosting/assembly_renderer_pipeline.s3" in completed.stdout
    assert "purpose: Assembly renderer pipeline model" in completed.stdout
    assert "examples/self_hosting/assembly_renderer_text_builder.s3" in completed.stdout
    assert "purpose: Assembly renderer text builder command model" in completed.stdout
    assert "examples/self_hosting/assembly_renderer_text_fragments.s3" in completed.stdout
    assert "purpose: Assembly renderer static text fragment model" in completed.stdout
    assert completed.stderr == ""
