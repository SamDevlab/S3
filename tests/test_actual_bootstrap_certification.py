from __future__ import annotations

import json
from pathlib import Path

from tools.certify_actual_bootstrap import certify, source_entries


ROOT = Path(__file__).parents[1]


def test_source_manifest_is_deterministic_and_nonempty(tmp_path: Path) -> None:
    assert source_entries(ROOT)
    first = certify(ROOT, tmp_path / "first")
    second = certify(ROOT, tmp_path / "second")
    assert first["source_manifest_sha256"] == second["source_manifest_sha256"]
    assert json.loads((tmp_path / "first" / "compiler-source-manifest.json").read_text()) == json.loads(
        (tmp_path / "second" / "compiler-source-manifest.json").read_text()
    )


def test_certification_fails_closed_without_stage0_compiler_artifact(tmp_path: Path) -> None:
    result = certify(ROOT, tmp_path / "evidence")
    assert result["actual_bootstrap_execution"] == "FAIL"
    assert result["full_self_hosting"] == "NO"
    assert result["first_blocking_gate"] == "STAGE0_TO_STAGE1"
    assert json.loads((tmp_path / "evidence" / "fail-closed-tests.json").read_text())["status"] == "PASS"
