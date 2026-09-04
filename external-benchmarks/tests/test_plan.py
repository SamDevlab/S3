from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.cli import main  # noqa: E402
from harness.core import ExternalBenchmarkError  # noqa: E402
from harness.plan import build_run_plan  # noqa: E402


def _campaign() -> dict[str, object]:
    return {
        "campaign_id": "agent-memory-v1",
        "version": "1.0.0",
        "configurations": [
            {"id": "no-memory"},
            {"id": "ai-memory"},
        ],
        "scenarios": [
            {"scenario_id": "one", "mode": "single-session"},
            {"scenario_id": "two", "mode": "cross-session"},
            {"scenario_id": "three", "mode": "cross-agent"},
            {
                "scenario_id": "four",
                "mode": "stale-memory",
                "stale_claim_id": "ffi-is-future-work",
            },
        ],
    }


def _build(**overrides: object) -> dict[str, object]:
    arguments: dict[str, object] = {
        "provider_id": "ai-memory",
        "provider_version": "2.x",
        "repetition": 2,
        "s3_commit": "abc123",
        "agent_provider": "openai",
        "agent_model": "fixture",
        "agent_harness": "codex",
        "agent_harness_version": "1",
        "tool_permissions_profile": "standard",
    }
    arguments.update(overrides)
    return build_run_plan(_campaign(), **arguments)  # type: ignore[arg-type]


def test_run_plan_is_deterministic_and_encodes_isolation() -> None:
    plan = _build()

    assert plan["run_root"] == "ai-memory/run-2"
    assert plan["execution"] == {
        "s3_commit": "abc123",
        "agent_harness_version": "1",
        "tool_permissions_profile": "standard",
        "task_protocol_version": "agent-memory-v1",
        "repetition": 2,
    }
    scenarios = plan["scenarios"]
    assert [row["scenario_id"] for row in scenarios] == ["one", "two", "three", "four"]
    assert scenarios[0]["worktree_key"] == "ai-memory/run-2/one"
    assert scenarios[1]["required_evidence"] == ["handoff"]
    assert scenarios[2]["template"].endswith("cross-agent.json")
    assert scenarios[3]["required_evidence"] == ["stale_memory"]
    assert scenarios[3]["stale_claim_id"] == "ffi-is-future-work"


def test_run_plan_rejects_undeclared_provider() -> None:
    with pytest.raises(ExternalBenchmarkError, match="not a declared campaign"):
        _build(provider_id="unknown")


def test_run_plan_rejects_invalid_repetition() -> None:
    with pytest.raises(ExternalBenchmarkError, match="positive integer"):
        _build(repetition=0)


def test_prepare_run_cli_uses_real_campaign_and_templates(tmp_path: Path) -> None:
    output = tmp_path / "plan.json"

    exit_code = main(
        [
            "--prepare-run",
            "--campaign",
            "agent-memory-v1",
            "--provider",
            "ai-memory",
            "--provider-version",
            "2.x",
            "--repetition",
            "1",
            "--s3-commit",
            "abc123",
            "--agent-provider",
            "openai",
            "--agent-model",
            "fixture",
            "--agent-harness",
            "codex",
            "--agent-harness-version",
            "1",
            "--tool-permissions-profile",
            "standard",
            "--output-json",
            str(output),
        ]
    )

    assert exit_code == 0
    plan = json.loads(output.read_text(encoding="utf-8"))
    assert plan["campaign_id"] == "agent-memory-v1"
    assert plan["provider"]["id"] == "ai-memory"
    assert len(plan["scenarios"]) == 7
    assert all(
        (EXTERNAL_ROOT / scenario["template"]).is_file()
        for scenario in plan["scenarios"]
    )
