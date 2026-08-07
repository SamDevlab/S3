from __future__ import annotations

import subprocess
import sys


def test_assembly_renderer_candidate_readiness_gate_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/check_assembly_renderer_candidate_readiness.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "fixtures: ok" in completed.stdout
    assert "fixture expectations: ok" in completed.stdout
    assert "comparison plan: ok" in completed.stdout
    assert "actual outputs: ok" in completed.stdout
    assert "candidate fixtures: ok" in completed.stdout
    assert "candidate fixture expectations: ok" in completed.stdout
    assert "candidate comparison plan: ok" in completed.stdout
    assert "candidate actual outputs: ok" in completed.stdout
    assert "candidate run: ok" in completed.stdout
    assert "comparison passed: ok" in completed.stdout
    assert "assembly renderer candidate readiness: ok" in completed.stdout
    assert completed.stderr == ""
