from __future__ import annotations

import subprocess
import sys


def test_golden_diagnostics_check_matches_committed_outputs() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/golden_diagnostics.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "golden diagnostics: checked 3 case(s)" in completed.stdout
    assert completed.stderr == ""
