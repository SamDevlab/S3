from __future__ import annotations

import json
import sys
from pathlib import Path

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.comparison import compare_campaign  # noqa: E402
from harness.report import render_comparison_markdown  # noqa: E402


def _campaign() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "campaign_id": "agent-memory-v1",
        "version": "1.0.0",
        "category": "agent-memory",
        "objective": "test",
        "configurations": [
            {"id": "no-memory", "description": "none"},
            {"id": "ai-memory", "description": "memory"},
        ],
        "protocol": {
            "worktree_isolation": "fresh-worktree-per-scenario",
            "recommended_repetitions": 2,
            "result_collection": "isolated",
            "rules": ["test"],
        },
        "scenarios": [
            {"scenario_id": "one", "mode": "single-session", "purpose": "one"},
            {"scenario_id": "two", "mode": "cross-agent", "purpose": "two"},
        ],
        "gates": {
            "require_all_oracles_pass": True,
            "recall_is_gate": False,
            "provider_consistency": True,
        },
    }


def _scenario(scenario_id: str, *, status: str, recall: float) -> dict[str, object]:
    row: dict[str, object] = {
        "schema_version": "1.0.0",
        "scenario_id": scenario_id,
        "scenario_version": "1.0.0",
        "category": "agent-memory",
        "agent": {"provider": "openai", "model": "fixture", "harness": "codex"},
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
        row["handoff"] = {
            "kind": "cross-agent",
            "source_agent": {
                "provider": "openai",
                "model": "fixture-a",
                "harness": "codex",
            },
            "target_agent": {
                "provider": "openai",
                "model": "fixture-b",
                "harness": "codex",
            },
            "transcript_reused": False,
        }
    return row


def _campaign_result(
    provider: str,
    repetition: int,
    *,
    fail_second: bool = False,
) -> dict[str, object]:
    first = _scenario("one", status="PASS", recall=1.0)
    second = _scenario(
        "two",
        status="FAIL" if fail_second else "PASS",
        recall=0.5,
    )
    return {
        "schema_version": "1.0.0",
        "campaign_id": "agent-memory-v1",
        "campaign_version": "1.0.0",
        "category": "agent-memory",
        "provider": {"id": provider, "version": "v1"},
        "execution": {
            "s3_commit": "abc123",
            "agent_harness_version": "1",
            "tool_permissions_profile": "standard",
            "task_protocol_version": "agent-memory-v1",
            "repetition": repetition,
        },
        "status": "FAIL" if fail_second else "PASS",
        "metrics": {
            "scenarios_total": 2,
            "scenarios_passed": 1 if fail_second else 2,
            "scenarios_failed": 1 if fail_second else 0,
            "critical_oracle_failures": 1 if fail_second else 0,
            "mean_invariant_recall_rate": 0.75,
        },
        "results": [first, second],
    }


def _write(
    root: Path,
    provider: str,
    repetition: int,
    document: dict[str, object],
) -> None:
    path = root / provider / f"run-{repetition}" / "campaign.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_comparison_is_neutral_and_comparable(tmp_path: Path) -> None:
    for repetition in (1, 2):
        _write(
            tmp_path,
            "no-memory",
            repetition,
            _campaign_result("no-memory", repetition, fail_second=True),
        )
        _write(
            tmp_path,
            "ai-memory",
            repetition,
            _campaign_result("ai-memory", repetition),
        )

    result = compare_campaign(_campaign(), comparison_root=tmp_path)

    assert result["status"] == "PASS"
    assert result["comparability"]["status"] == "COMPARABLE"
    assert result["providers"]["no-memory"]["scenario_pass_rate"] == 0.5
    assert result["providers"]["ai-memory"]["scenario_pass_rate"] == 1.0
    report = render_comparison_markdown(result)
    assert "does not select a winner" in report
    assert "`no-memory`" in report
    assert "`ai-memory`" in report


def test_comparison_blocks_claims_when_execution_differs(tmp_path: Path) -> None:
    for repetition in (1, 2):
        _write(
            tmp_path,
            "no-memory",
            repetition,
            _campaign_result("no-memory", repetition),
        )
        document = _campaign_result("ai-memory", repetition)
        if repetition == 2:
            document["execution"]["s3_commit"] = "different"  # type: ignore[index]
        _write(tmp_path, "ai-memory", repetition, document)

    result = compare_campaign(_campaign(), comparison_root=tmp_path)

    assert result["status"] == "FAIL"
    assert result["comparability"]["status"] == "NOT_COMPARABLE"
    assert any(
        "execution.s3_commit differs" in reason
        for reason in result["comparability"]["reasons"]
    )


def test_comparison_blocks_claims_when_agent_identity_differs(tmp_path: Path) -> None:
    for repetition in (1, 2):
        _write(
            tmp_path,
            "no-memory",
            repetition,
            _campaign_result("no-memory", repetition),
        )
        document = _campaign_result("ai-memory", repetition)
        if repetition == 1:
            document["results"][0]["agent"]["model"] = "different"  # type: ignore[index]
        _write(tmp_path, "ai-memory", repetition, document)

    result = compare_campaign(_campaign(), comparison_root=tmp_path)

    assert result["comparability"]["status"] == "NOT_COMPARABLE"
    assert any(
        "agent identity differs" in reason
        for reason in result["comparability"]["reasons"]
    )
