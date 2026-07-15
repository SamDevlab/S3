from __future__ import annotations

import subprocess
import sys


def test_string_capability_inventory_reports_stable_heading() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/string_capability_inventory.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "S3 string capability inventory" in completed.stdout
    assert completed.stderr == ""
