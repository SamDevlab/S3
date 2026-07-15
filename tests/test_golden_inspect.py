from __future__ import annotations

import subprocess
import sys


def test_golden_inspect_check_matches_committed_outputs() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/golden_inspect.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "golden inspect: checked 1 example(s)" in completed.stdout
    assert completed.stderr == ""
