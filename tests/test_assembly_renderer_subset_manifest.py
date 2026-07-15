from __future__ import annotations

import subprocess
import sys


def test_assembly_renderer_subset_manifest_matches_current_goldens() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/check_assembly_renderer_subset_manifest.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "assembly renderer subset manifest: ok" in completed.stdout
    assert completed.stderr == ""
