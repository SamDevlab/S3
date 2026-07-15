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
    assert "s3 program check: checked 3 program(s)" in completed.stdout
    assert completed.stderr == ""
