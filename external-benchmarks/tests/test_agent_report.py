from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.agent_report import load_agent_report  # noqa: E402
from harness.core import ExternalBenchmarkError  # noqa: E402


def test_agent_report_is_minimal_and_sorted(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "reported_invariants": ["z", "a"],
            }
        ),
        encoding="utf-8",
    )
    result = load_agent_report(path)
    assert result == {
        "schema_version": "1.0.0",
        "reported_invariants": ["a", "z"],
    }


def test_agent_report_rejects_transcript_or_other_extra_fields(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "reported_invariants": [],
                "transcript": "must not persist",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ExternalBenchmarkError, match="forbidden fields"):
        load_agent_report(path)


def test_agent_report_rejects_duplicate_invariants(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "reported_invariants": ["same", "same"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ExternalBenchmarkError, match="must be unique"):
        load_agent_report(path)


def test_agent_report_rejects_oversized_input(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(" " * (16 * 1024 + 1), encoding="utf-8")
    with pytest.raises(ExternalBenchmarkError, match="size limit"):
        load_agent_report(path)
