from __future__ import annotations

import subprocess
import sys


def test_assembly_renderer_candidate_comparison_plan_manifest_is_valid() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/check_assembly_renderer_candidate_comparison_plan.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "assembly renderer candidate comparison plan: ok" in completed.stdout
    assert completed.stderr == ""
