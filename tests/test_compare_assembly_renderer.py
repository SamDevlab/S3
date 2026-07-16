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
    assert "implements renderer: no" in completed.stdout
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
