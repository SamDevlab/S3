from __future__ import annotations

import subprocess
import sys


def test_assembly_renderer_candidate_actual_outputs_manifest_is_valid() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/check_assembly_renderer_candidate_actual_outputs.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "assembly renderer candidate actual outputs: ok" in completed.stdout
    assert completed.stderr == ""
