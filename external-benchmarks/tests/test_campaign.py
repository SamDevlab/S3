from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.campaign import aggregate_campaign, list_campaigns, load_campaign  # noqa: E402
from harness.core import ExternalBenchmarkError, load_scenario  # noqa: E402

SUBJECT = "a" * 40


def _campaign() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "campaign_id": "test-campaign",
        "version": "1.0.0",
        "category": "agent-memory",
        "objective": "test",
        "configurations": [
            {"id": "provider-a", "description": "test provider A"},
            {"id": "provider-b", "description": "test provider B"},
        ],
        "protocol": {
            "subject_commit": SUBJECT,
            "worktree_isolation": "fresh-worktree-per-scenario",
            "recommended_repetitions": 1,
            "result_collection": "isolated",
            "rules": ["test rule"],
        },
        "scenarios": [
            {"scenario_id": "one", "mode": "single-session", "purpose": "one"},
            {"scenario_id": "two", "mode": "cross-session", "purpose": "two"},
        ],
        "gates": {
            "require_all_oracles_pass": True,
            "recall_is_gate": False,
            "provider_consistency": True,
        },
    }


def _execution(repetition: int = 1, *, commit: str = SUBJECT) -> dict[str, object]:
    return {
        "s3_commit": commit,
        "agent_harness_version": "1",
        "tool_permissions_profile": "standard",
        "task_protocol_version": "agent-memory-v1",
        "repetition": repetition,
    }


def _result(
    scenario_id: str,
    *,
    provider: str = "provider-a",
    status: str = "PASS",
    recall: float = 1.0,
    repetition: int = 1,
    commit: str = SUBJECT,
) -> dict[str, object]:
    result: dict[str, object] = {
        "schema_version": "1.0.0",
        "scenario_id": scenario_id,
        "scenario_version": "1.0.0",
        "category": "agent-memory",
        "provider": {"id": provider, "version": "1"},
        "agent": {"provider": "test", "model": "fixture", "harness": "pytest"},
        "execution": _execution(repetition, commit=commit),
        "status": status,
        "reported_invariants": [],
        "metrics": {
            "critical_invariants_total": 1,
            "critical_invariants_reported": int(recall > 0),
            "invariant_recall_rate": recall,
            "oracle_checks_total": 1,
            "oracle_checks_passed": int(status == "PASS"),
            "critical_oracle_failures": int(status == "FAIL"),
        },
        "oracle": [],
    }
    if scenario_id == "two":
        result["handoff"] = {
            "kind": "cross-session",
            "source_agent": {"provider": "test", "model": "fixture", "harness": "pytest-a"},
            "target_agent": {"provider": "test", "model": "fixture", "harness": "pytest-b"},
            "transcript_reused": False,
        }
    return result


def _write_results(tmp_path: Path, first: dict[str, object], second: dict[str, object]) -> None:
    (tmp_path / "one.json").write_text(json.dumps(first), encoding="utf-8")
    (tmp_path / "two.json").write_text(json.dumps(second), encoding="utf-8")


def test_campaign_aggregation_is_correctness_first(tmp_path: Path) -> None:
    _write_results(tmp_path, _result("one"), _result("two", status="FAIL"))
    result = aggregate_campaign(_campaign(), result_dir=tmp_path)
    assert result["status"] == "FAIL"
    assert result["execution"] == _execution()
    assert result["metrics"]["critical_oracle_failures"] == 1


def test_campaign_rejects_mixed_provider_results(tmp_path: Path) -> None:
    _write_results(
        tmp_path,
        _result("one", provider="provider-a"),
        _result("two", provider="provider-b"),
    )
    with pytest.raises(ExternalBenchmarkError, match="one provider configuration"):
        aggregate_campaign(_campaign(), result_dir=tmp_path)


def test_campaign_rejects_subject_commit_drift(tmp_path: Path) -> None:
    _write_results(
        tmp_path,
        _result("one"),
        _result("two", commit="b" * 40),
    )
    with pytest.raises(ExternalBenchmarkError, match="subject_commit"):
        aggregate_campaign(_campaign(), result_dir=tmp_path)


def test_campaign_rejects_transcript_reuse(tmp_path: Path) -> None:
    first = _result("one")
    second = _result("two")
    second["handoff"]["transcript_reused"] = True  # type: ignore[index]
    _write_results(tmp_path, first, second)
    with pytest.raises(ExternalBenchmarkError, match="transcript reuse is forbidden"):
        aggregate_campaign(_campaign(), result_dir=tmp_path)


def test_campaign_listing_is_deterministic(tmp_path: Path) -> None:
    first = _campaign()
    second = dict(first)
    second["campaign_id"] = "z-campaign"
    (tmp_path / "b.json").write_text(json.dumps(second), encoding="utf-8")
    (tmp_path / "a.json").write_text(json.dumps(first), encoding="utf-8")
    rows = list_campaigns(tmp_path)
    assert [row["campaign_id"] for row in rows] == ["test-campaign", "z-campaign"]


def test_agent_memory_v1_is_frozen_and_references_existing_unique_scenarios() -> None:
    campaign = load_campaign(EXTERNAL_ROOT / "campaigns" / "agent-memory-v1.json")
    scenario_ids = [entry["scenario_id"] for entry in campaign["scenarios"]]
    discovered = {
        load_scenario(path)["scenario_id"]
        for path in sorted((EXTERNAL_ROOT / "scenarios").glob("*.json"))
    }
    assert campaign["campaign_id"] == "agent-memory-v1"
    assert campaign["protocol"]["subject_commit"] == "db5f4bf10e2066f52bf144d23e6f7db56154e298"
    assert len(scenario_ids) == 7 == len(set(scenario_ids))
    assert set(scenario_ids).issubset(discovered)
    assert [configuration["id"] for configuration in campaign["configurations"]] == [
        "no-memory",
        "context-only",
        "ai-memory",
        "ai-memory+s3-integrity-gate",
    ]
    stale = next(entry for entry in campaign["scenarios"] if entry["mode"] == "stale-memory")
    assert stale["stale_claim_id"] == "ffi-is-future-work"
