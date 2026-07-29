from __future__ import annotations

import subprocess
import sys


def test_compare_assembly_renderer_status_reports_blocked_state() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/compare_assembly_renderer.py", "--status"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "S3 Assembly renderer comparison harness" in completed.stdout
    assert "s3 renderer stub: available" in completed.stdout
    assert "s3 renderer bootstrap spike: available" in completed.stdout
    assert "s3 renderer output model: available" in completed.stdout
    assert "s3 renderer text segment model: available" in completed.stdout
    assert "s3 renderer line blueprint model: available" in completed.stdout
    assert "s3 renderer line sequence model: available" in completed.stdout
    assert "s3 renderer line content encoding model: available" in completed.stdout
    assert "s3 renderer event stream model: available" in completed.stdout
    assert "s3 renderer event writer model: available" in completed.stdout
    assert "s3 renderer output buffer model: available" in completed.stdout
    assert "s3 renderer pipeline model: available" in completed.stdout
    assert "s3 renderer text builder model: available" in completed.stdout
    assert "s3 renderer static text fragment model: available" in completed.stdout
    assert "s3 renderer implementation: not implemented" in completed.stdout
    assert "typed static text values: available" in completed.stdout
    assert "string runtime support" not in completed.stdout
    assert "status: blocked" in completed.stdout
    assert completed.stderr == ""


def test_compare_assembly_renderer_reference_reports_available_reference() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/compare_assembly_renderer.py", "--reference"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "S3 Assembly renderer Python reference" in completed.stdout
    assert "status: available" in completed.stdout
    assert "examples/first.s3" in completed.stdout
    assert "tests/golden/inspect/first.assembly.txt" in completed.stdout
    assert completed.stderr == ""


def test_compare_assembly_renderer_candidate_reports_stub() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/compare_assembly_renderer.py", "--candidate"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "S3 Assembly renderer candidate" in completed.stdout
    assert "status: stub" in completed.stdout
    assert "entrypoint: main" in completed.stdout
    assert "status function: renderer_candidate_status" in completed.stdout
    assert (
        "directive count function: renderer_supported_directive_count"
        in completed.stdout
    )
    assert (
        "opcode count function: renderer_supported_opcode_count"
        in completed.stdout
    )
    assert (
        "capability smoke function: renderer_candidate_capability_smoke"
        in completed.stdout
    )
    assert "directive id functions: 6" in completed.stdout
    assert "opcode id functions: 7" in completed.stdout
    assert "directive id range: 0..5" in completed.stdout
    assert "opcode id range: 0..6" in completed.stdout
    assert (
        "directive support predicate: renderer_supports_directive_id"
        in completed.stdout
    )
    assert (
        "opcode support predicate: renderer_supports_opcode_id"
        in completed.stdout
    )
    assert "implements renderer: no" in completed.stdout
    assert completed.stderr == ""


def test_compare_assembly_renderer_candidate_symbols_reports_table() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/compare_assembly_renderer.py", "--candidate-symbols"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "S3 Assembly renderer candidate symbols" in completed.stdout
    assert "directives:" in completed.stdout
    assert "0 .end renderer_directive_end_id" in completed.stdout
    assert "5 .s3asm renderer_directive_s3asm_id" in completed.stdout
    assert "opcodes:" in completed.stdout
    assert "0 TADD renderer_opcode_tadd_id" in completed.stdout
    assert "6 TRET renderer_opcode_tret_id" in completed.stdout
    assert "directive id range: 0..5" in completed.stdout
    assert "opcode id range: 0..6" in completed.stdout
    assert "status: stub" in completed.stdout
    assert "comparison: blocked" in completed.stdout
    assert completed.stderr == ""


def test_compare_assembly_renderer_candidate_fixtures_reports_contract() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/compare_assembly_renderer.py", "--candidate-fixtures"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "S3 Assembly renderer candidate fixtures" in completed.stdout
    assert "fixtures:" in completed.stdout
    assert "first examples/first.s3" in completed.stdout
    assert "simple_call examples/simple_call.s3" in completed.stdout
    assert "sign examples/sign.s3" in completed.stdout
    assert "excluded:" in completed.stdout
    assert "assembly_renderer_stub" in completed.stdout
    assert "status: reference_only" in completed.stdout
    assert "comparison: blocked" in completed.stdout
    assert completed.stderr == ""


def test_compare_assembly_renderer_candidate_fixture_expectations_reports_contract() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "tools/compare_assembly_renderer.py",
            "--candidate-fixture-expectations",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert (
        "S3 Assembly renderer candidate fixture expectations"
        in completed.stdout
    )
    assert "expectations:" in completed.stdout
    assert "first tests/golden/inspect/first.assembly.txt" in completed.stdout
    assert (
        "simple_call tests/golden/inspect/simple_call.assembly.txt"
        in completed.stdout
    )
    assert "sign tests/golden/inspect/sign.assembly.txt" in completed.stdout
    assert "sha256=" in completed.stdout
    assert "bytes=" in completed.stdout
    assert "lines=" in completed.stdout
    assert (
        "source manifest: tests/golden/assembly_renderer_candidate_fixtures.json"
        in completed.stdout
    )
    assert "status: reference_only" in completed.stdout
    assert "comparison: blocked" in completed.stdout
    assert completed.stderr == ""


def test_compare_assembly_renderer_candidate_comparison_plan_reports_contract() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "tools/compare_assembly_renderer.py",
            "--candidate-comparison-plan",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "S3 Assembly renderer candidate comparison plan" in completed.stdout
    assert (
        "fixture expectations: "
        "tests/golden/assembly_renderer_candidate_fixture_expectations.json"
        in completed.stdout
    )
    assert (
        "first expected=tests/golden/inspect/first.assembly.txt"
        in completed.stdout
    )
    assert (
        "simple_call expected=tests/golden/inspect/simple_call.assembly.txt"
        in completed.stdout
    )
    assert (
        "sign expected=tests/golden/inspect/sign.assembly.txt"
        in completed.stdout
    )
    assert "sha256=" in completed.stdout
    assert "first expected=tests/golden/inspect/first.assembly.txt" in completed.stdout
    assert "actual=available comparison=passed" in completed.stdout
    assert (
        "simple_call expected=tests/golden/inspect/simple_call.assembly.txt"
        in completed.stdout
    )
    assert "actual=available comparison=passed" in completed.stdout
    assert "sign expected=tests/golden/inspect/sign.assembly.txt" in completed.stdout
    assert "actual=available comparison=passed" in completed.stdout
    assert "comparison: blocked" in completed.stdout
    assert "expected output: assembly_golden" in completed.stdout
    assert "actual output: s3_renderer_candidate" in completed.stdout
    assert "actual output status: not_implemented" in completed.stdout
    assert "status: blocked" in completed.stdout
    assert completed.stderr == ""


def test_compare_assembly_renderer_candidate_actual_outputs_reports_contract() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "tools/compare_assembly_renderer.py",
            "--candidate-actual-outputs",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "S3 Assembly renderer candidate actual outputs" in completed.stdout
    assert (
        "comparison plan: "
        "tests/golden/assembly_renderer_candidate_comparison_plan.json"
        in completed.stdout
    )
    assert (
        "actual output root: tests/golden/assembly_renderer_candidate_actual"
        in completed.stdout
    )
    assert (
        "first planned=tests/golden/assembly_renderer_candidate_actual/first.assembly.txt"
        in completed.stdout
    )
    assert "exists=true" in completed.stdout
    assert "status=available" in completed.stdout
    assert "comparison=passed" in completed.stdout
    assert (
        "sha256=a144d584ed40287d10cff5ecc50a170823aac7ddd0a7fed455837b936131a90f"
        in completed.stdout
    )
    assert "bytes=377" in completed.stdout
    assert "lines=16" in completed.stdout
    assert (
        "simple_call planned=tests/golden/assembly_renderer_candidate_actual/simple_call.assembly.txt"
        in completed.stdout
    )
    assert (
        "simple_call planned=tests/golden/assembly_renderer_candidate_actual/simple_call.assembly.txt "
        "exists=true status=available comparison=passed "
        "sha256=d6de00c8c50618bcc8f3a458267eb8590956a9451980084b1add2f59d3267c0f "
        "bytes=448 lines=21"
        in completed.stdout
    )
    assert (
        "sign planned=tests/golden/assembly_renderer_candidate_actual/sign.assembly.txt"
        in completed.stdout
    )
    assert (
        "sign planned=tests/golden/assembly_renderer_candidate_actual/sign.assembly.txt "
        "exists=true status=available comparison=passed "
        "sha256=2002bbcdf4f893efafb34d3e194dd6b5602eb2d023a2d0d064a5d2642d48f880 "
        "bytes=829 lines=32"
        in completed.stdout
    )
    assert "status: partial" in completed.stdout
    assert completed.stderr == ""


def test_compare_assembly_renderer_candidate_compare_available_reports_first_passed() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "tools/compare_assembly_renderer.py",
            "--candidate-compare-available",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert (
        "S3 Assembly renderer candidate available comparisons"
        in completed.stdout
    )
    assert (
        "first expected=tests/golden/inspect/first.assembly.txt "
        "actual=tests/golden/assembly_renderer_candidate_actual/first.assembly.txt "
        "status=passed"
        in completed.stdout
    )
    assert (
        "sha256=a144d584ed40287d10cff5ecc50a170823aac7ddd0a7fed455837b936131a90f"
        in completed.stdout
    )
    assert "bytes=377" in completed.stdout
    assert "lines=16" in completed.stdout
    assert (
        "simple_call expected=tests/golden/inspect/simple_call.assembly.txt "
        "actual=tests/golden/assembly_renderer_candidate_actual/simple_call.assembly.txt "
        "status=passed"
        in completed.stdout
    )
    assert (
        "sign expected=tests/golden/inspect/sign.assembly.txt "
        "actual=tests/golden/assembly_renderer_candidate_actual/sign.assembly.txt "
        "status=passed"
        in completed.stdout
    )
    assert "available comparisons: 3" in completed.stdout
    assert "passed comparisons: 3" in completed.stdout
    assert "pending comparisons: 0" in completed.stdout
    assert "blocked comparisons: 0" in completed.stdout
    assert "status: partial" in completed.stdout
    assert "comparison: partial" in completed.stdout
    assert completed.stderr == ""


def test_compare_assembly_renderer_candidate_run_executes_stub_status() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/compare_assembly_renderer.py", "--candidate-run"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "S3 Assembly renderer candidate execution" in completed.stdout
    assert "path: examples/self_hosting/assembly_renderer_stub.s3" in completed.stdout
    assert "entrypoint: main" in completed.stdout
    assert "expected status: -1" in completed.stdout
    assert "actual status: -1" in completed.stdout
    assert "covered by s3_program_check: yes" in completed.stdout
    assert "status: stub" in completed.stdout
    assert "candidate renderer bootstrap: available" in completed.stdout
    assert "s3 bootstrap spike: passed" in completed.stdout
    assert (
        "program: examples/self_hosting/assembly_renderer_bootstrap.s3"
        in completed.stdout
    )
    assert "expected return: 0" in completed.stdout
    assert "actual return: 0" in completed.stdout
    assert "s3 output model: passed" in completed.stdout
    assert (
        "program: examples/self_hosting/assembly_renderer_output_model.s3"
        in completed.stdout
    )
    assert "s3 text segment model: passed" in completed.stdout
    assert (
        "program: examples/self_hosting/assembly_renderer_text_segments.s3"
        in completed.stdout
    )
    assert "s3 line blueprint model: passed" in completed.stdout
    assert (
        "program: examples/self_hosting/assembly_renderer_line_blueprints.s3"
        in completed.stdout
    )
    assert "s3 line sequence model: passed" in completed.stdout
    assert (
        "program: examples/self_hosting/assembly_renderer_line_sequences.s3"
        in completed.stdout
    )
    assert "s3 line content encoding model: passed" in completed.stdout
    assert (
        "program: examples/self_hosting/assembly_renderer_line_encodings.s3"
        in completed.stdout
    )
    assert "s3 event stream model: passed" in completed.stdout
    assert (
        "program: examples/self_hosting/assembly_renderer_event_stream.s3"
        in completed.stdout
    )
    assert "s3 event writer model: passed" in completed.stdout
    assert (
        "program: examples/self_hosting/assembly_renderer_event_writer.s3"
        in completed.stdout
    )
    assert "s3 output buffer model: passed" in completed.stdout
    assert (
        "program: examples/self_hosting/assembly_renderer_output_buffer.s3"
        in completed.stdout
    )
    assert "s3 renderer pipeline model: passed" in completed.stdout
    assert (
        "program: examples/self_hosting/assembly_renderer_pipeline.s3"
        in completed.stdout
    )
    assert "s3 text builder model: passed" in completed.stdout
    assert (
        "program: examples/self_hosting/assembly_renderer_text_builder.s3"
        in completed.stdout
    )
    assert "s3 text fragment model: passed" in completed.stdout
    assert (
        "program: examples/self_hosting/assembly_renderer_text_fragments.s3"
        in completed.stdout
    )
    assert "renderer implementation: not_implemented" in completed.stdout
    assert "full text rendering: not_implemented" in completed.stdout
    assert completed.stderr == ""


def test_compare_assembly_renderer_check_passes_with_s3_renderer() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/compare_assembly_renderer.py", "--check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "S3 Assembly renderer comparison check: ok" in completed.stdout
    assert "actual outputs: passed" in completed.stdout
    assert "available comparisons: passed" in completed.stdout
    assert "renderer implementation: complete" in completed.stdout
    assert "full text rendering: passed" in completed.stdout
    assert "global check: passed" in completed.stdout
    assert completed.stderr == ""


def test_candidate_render_first_uses_legacy_fixture(monkeypatch) -> None:
    from tools import compare_assembly_renderer
    from tools.s3_renderer_contract import FIXTURE_METADATA

    calls = []

    def fake_render(*args, **kwargs):
        calls.append((args, kwargs))
        return 0

    monkeypatch.setattr(
        compare_assembly_renderer, "_render_s3_fixture", fake_render
    )

    assert compare_assembly_renderer.candidate_render_first() == 0

    meta = FIXTURE_METADATA["first"]
    assert calls == [
        (
            (meta.s3_path, meta.golden_path, "first"),
            {
                "buffer_count": meta.buffer_count,
                "buffer_offset": meta.buffer_offset,
                "entry": meta.entry,
                "max_instructions": meta.max_instructions,
                "expected_bytes": meta.expected_bytes,
            },
        )
    ]
