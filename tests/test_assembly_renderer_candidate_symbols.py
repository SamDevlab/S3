from __future__ import annotations

import subprocess
import sys


def test_assembly_renderer_candidate_symbols_matches_golden() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/check_assembly_renderer_candidate_symbols.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "assembly renderer candidate symbols: ok" in completed.stdout
    assert completed.stderr == ""
