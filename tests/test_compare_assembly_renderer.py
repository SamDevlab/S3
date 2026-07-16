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
    assert "s3 renderer implementation: not implemented" in completed.stdout
    assert (
        "string literals: front-end only, runtime not implemented"
        in completed.stdout
    )
    assert "string runtime support" in completed.stdout
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
    assert "opcode id functions: 8" in completed.stdout
    assert "directive id range: 0..5" in completed.stdout
    assert "opcode id range: 0..7" in completed.stdout
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
    assert "7 TRET renderer_opcode_tret_id" in completed.stdout
    assert "directive id range: 0..5" in completed.stdout
    assert "opcode id range: 0..7" in completed.stdout
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
    assert completed.stderr == ""


def test_compare_assembly_renderer_check_fails_until_s3_renderer_exists() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/compare_assembly_renderer.py", "--check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "S3 renderer is not implemented" in completed.stdout
    assert completed.stderr == ""
