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
    assert "status: blocked" in completed.stdout
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
