from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.reliability_contract_v2 import canonical_json_document
from tools.reliability_triage_v2 import (
    TRIAGE_SCHEMA,
    build_triage_report,
    group_failures,
    render_triage_markdown,
    write_triage_report,
)


pytestmark = pytest.mark.s3_contract


def _failure(case_id: str, index: int, outcome: str, signature: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "case_index": index,
        "outcome": outcome,
        "failure_signature": signature,
    }


def test_failure_groups_are_deduplicated_and_sorted_by_frozen_key() -> None:
    results = [
        _failure("d" * 64, 7, "TIMEOUT", "timeout:RUN_HOSTED:hosted:O0:5000"),
        {"case_id": "p" * 64, "case_index": 1, "outcome": "PASS", "failure_signature": None},
        _failure("b" * 64, 5, "MISCOMPILE", "miscompile:second"),
        _failure("a" * 64, 2, "MISCOMPILE", "miscompile:first"),
        _failure("c" * 64, 3, "MISCOMPILE", "miscompile:first"),
        _failure("e" * 64, 8, "TIMEOUT", "timeout:RUN_HOSTED:hosted:O0:5000"),
    ]

    groups = group_failures(results)

    assert [(group.outcome, group.failure_signature, group.first_case_index) for group in groups] == [
        ("MISCOMPILE", "miscompile:first", 2),
        ("MISCOMPILE", "miscompile:second", 5),
        ("TIMEOUT", "timeout:RUN_HOSTED:hosted:O0:5000", 7),
    ]
    assert groups[0].count == 2
    assert groups[0].case_ids == ("a" * 64, "c" * 64)
    assert groups[2].case_ids == ("d" * 64, "e" * 64)


def test_machine_and_markdown_reports_share_deterministic_model(tmp_path: Path) -> None:
    campaign = {
        "schema": "s3.reliability.differential-campaign.v1",
        "campaign_id": "r4-synthetic",
        "campaign_seed": 20260916,
        "compiler_head": "a" * 40,
        "native_case_count": 1,
        "confirmation_runs_per_path": 2,
        "results": [
            _failure("b" * 64, 1, "CRASH", "crash:RUN_HOSTED:exit-1"),
            {"case_id": "a" * 64, "case_index": 0, "outcome": "PASS", "failure_signature": None},
        ],
    }
    first = build_triage_report(campaign)
    second = build_triage_report(json.loads(canonical_json_document(campaign)))

    assert first == second
    assert first["schema"] == TRIAGE_SCHEMA
    assert first["failure_groups"][0]["outcome"] == "CRASH"
    markdown = render_triage_markdown(first)
    assert "CRASH" in markdown
    assert "crash:RUN_HOSTED:exit-1" in markdown
    assert "No failure groups" not in markdown

    path = tmp_path / "triage.json"
    write_triage_report(path, first)
    assert path.read_bytes() == canonical_json_document(first)


def test_triage_rejects_failure_without_signature() -> None:
    with pytest.raises(ValueError, match="failure_signature"):
        group_failures([_failure("a" * 64, 0, "CRASH", "")])

