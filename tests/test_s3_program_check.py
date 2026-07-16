from __future__ import annotations

import subprocess
import sys


def test_s3_program_check_matches_registered_programs() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/s3_program_check.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "s3 program check: checked 4 program(s)" in completed.stdout
    assert (
        "s3 program check: hosted execution checked 1 program(s)"
        in completed.stdout
    )
    assert "examples/self_hosting/assembly_renderer_stub.s3" in completed.stdout
    assert "hosted expected return: -1" in completed.stdout
    assert "hosted actual return: -1" in completed.stdout
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
    assert completed.stderr == ""
