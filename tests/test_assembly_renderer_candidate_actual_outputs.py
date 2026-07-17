from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ACTUAL_OUTPUTS = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_actual_outputs.json"
)


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


def test_simple_call_actual_output_contract_is_available_passed() -> None:
    data = json.loads(ACTUAL_OUTPUTS.read_text(encoding="utf-8"))
    rows = {item["name"]: item for item in data["outputs"]}

    assert rows["first"]["actual_output_status"] == "available"
    assert rows["first"]["comparison_status"] == "passed"
    assert rows["simple_call"]["actual_output_status"] == "available"
    assert rows["simple_call"]["actual_output_exists"] is True
    assert rows["simple_call"]["comparison_status"] == "passed"
    assert rows["simple_call"]["actual_byte_count"] == 448
    assert rows["simple_call"]["actual_line_count"] == 21
    assert (
        rows["simple_call"]["actual_sha256"]
        == "d6de00c8c50618bcc8f3a458267eb8590956a9451980084b1add2f59d3267c0f"
    )
    assert rows["sign"]["actual_output_status"] == "not_implemented"
    assert rows["sign"]["actual_output_exists"] is False
    assert rows["sign"]["comparison_status"] == "blocked"
    assert "actual_sha256" not in rows["sign"]
    assert "actual_byte_count" not in rows["sign"]
    assert "actual_line_count" not in rows["sign"]
