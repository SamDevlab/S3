from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.campaign import aggregate_campaign, list_campaigns, load_campaign  # noqa: E402
from harness.core import ExternalBenchmarkError, load_scenario  # noqa: E402


def _campaign() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "campaign_id": "test-campaign",
        "version": "1.0.0",
        "category": "agent-memory",
        "objective": "test",
        "configurations": [{"id": "provider-a", "description": "test provider"}],
        "protocol": {
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


def _result(scenario_id: str, *, provider: str = "provider-a", status: str = "PASS", recall: float = 1.0) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "scenario_id": scenario_id,
        "scenario_version": "1.0.0",
        "category": "agent-memory",
        "provider": {"id": provider, "version": "1"},
        "agent": {"provider": "test", "model": "fixture", "harness": "pytest"},
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


def test_campaign_aggregation_is_correctness_first(tmp_path: Path) -> None:
    (tmp_path / "one.json").write_text(json.dumps(_result("one", recall=1.0)), encoding="utf-8")
    (tmp_path / "two.json").write_text(
        json.dumps(_result("two", status="FAIL", recall=1.0)), encoding="utf-8"
    )

    result = aggregate_campaign(_campaign(), result_dir=tmp_path)

    assert result["status"] == "FAIL"
    assert result["metrics"]["scenarios_passed"] == 1
    assert result["metrics"]["scenarios_failed"] == 1
    assert result["metrics"]["critical_oracle_failures"] == 1
    assert result["metrics"]["mean_invariant_recall_rate"] == 1.0


def test_campaign_rejects_mixed_provider_results(tmp_path: Path) -> None:
    (tmp_path / "one.json").write_text(json.dumps(_result("one", provider="provider-a")), encoding="utf-8")
    (tmp_path / "two.json").write_text(json.dumps(_result("two", provider="provider-b")), encoding="utf-8")

    with pytest.raises(ExternalBenchmarkError, match="one provider configuration"):
        aggregate_campaign(_campaign(), result_dir=tmp_path)


def test_campaign_listing_is_deterministic(tmp_path: Path) -> None:
    first = _campaign()
    second = dict(first)
    second["campaign_id"] = "z-campaign"
    (tmp_path / "b.json").write_text(json.dumps(second), encoding="utf-8")
    (tmp_path / "a.json").write_text(json.dumps(first), encoding="utf-8")

    rows = list_campaigns(tmp_path)

    assert [row["campaign_id"] for row in rows] == ["test-campaign", "z-campaign"]


def test_agent_memory_v1_references_existing_unique_scenarios() -> None:
    campaign = load_campaign(EXTERNAL_ROOT / "campaigns" / "agent-memory-v1.json")
    scenario_ids = [entry["scenario_id"] for entry in campaign["scenarios"]]
    discovered = {
        load_scenario(path)["scenario_id"]
        for path in sorted((EXTERNAL_ROOT / "scenarios").glob("*.json"))
    }

    assert campaign["campaign_id"] == "agent-memory-v1"
    assert len(scenario_ids) == 7
    assert len(scenario_ids) == len(set(scenario_ids))
    assert set(scenario_ids).issubset(discovered)
    assert [configuration["id"] for configuration in campaign["configurations"]] == [
        "no-memory",
        "context-only",
        "ai-memory",
        "ai-memory+s3-integrity-gate",
    ]
    assert campaign["gates"] == {
        "require_all_oracles_pass": True,
        "recall_is_gate": False,
        "provider_consistency": True,
    }
