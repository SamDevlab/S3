from __future__ import annotations

import subprocess
import sys

from tools.s3_program_check import find_program, get_program_inventory


def test_s3_program_check_inventory_exposes_renderer_stub_hosted_check() -> None:
    programs = get_program_inventory()
    stub = find_program("examples/self_hosting/assembly_renderer_stub.s3")
    bootstrap = find_program(
        "examples/self_hosting/assembly_renderer_bootstrap.s3"
    )
    output_model = find_program(
        "examples/self_hosting/assembly_renderer_output_model.s3"
    )

    assert len(programs) == 6
    assert stub is not None
    assert stub.hosted_expected_return == -1
    assert bootstrap is not None
    assert bootstrap.hosted_expected_return == 0
    assert output_model is not None
    assert output_model.hosted_expected_return == 0


def test_s3_program_check_matches_registered_programs() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/s3_program_check.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "s3 program check: checked 6 program(s)" in completed.stdout
    assert (
        "s3 program check: hosted execution checked 3 program(s)"
        in completed.stdout
    )
    assert "examples/self_hosting/assembly_renderer_stub.s3" in completed.stdout
    assert "hosted expected return: -1" in completed.stdout
    assert "hosted actual return: -1" in completed.stdout
    assert "examples/self_hosting/assembly_renderer_bootstrap.s3" in completed.stdout
    assert "hosted expected return: 0" in completed.stdout
    assert "hosted actual return: 0" in completed.stdout
    assert "examples/self_hosting/assembly_renderer_output_model.s3" in completed.stdout
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
    assert completed.stderr == ""
