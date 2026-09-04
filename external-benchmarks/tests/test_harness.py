from __future__ import annotations

import json
import sys
from pathlib import Path

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.core import evaluate_scenario, list_scenarios  # noqa: E402


def _scenario() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "scenario_id": "test.memory.v1",
        "version": "1.0.0",
        "category": "agent-memory",
        "objective": "test",
        "critical_invariants": [
            {"id": "remember-me", "description": "test invariant"}
        ],
        "oracle": {
            "required_patterns": [
                {"id": "required", "glob": "src/**/*.py", "pattern": "safe_call"}
            ],
            "forbidden_patterns": [
                {"id": "forbidden", "glob": "src/**/*.py", "pattern": "shell=True"}
            ],
        },
    }


def _observation() -> dict[str, object]:
    return {
        "provider": {"id": "ai-memory", "version": "2.x"},
        "agent": {"provider": "test", "model": "fixture", "harness": "pytest"},
        "execution": {
            "s3_commit": "abc123",
            "agent_harness_version": "1",
            "tool_permissions_profile": "standard",
            "task_protocol_version": "agent-memory-v1",
            "repetition": 1,
            "token": "must-not-persist",
        },
        "reported_invariants": ["remember-me"],
    }


def test_oracle_passes_and_reports_recall(tmp_path: Path) -> None:
    source = tmp_path / "src" / "pkg" / "module.py"
    source.parent.mkdir(parents=True)
    source.write_text("def safe_call():\n    return 1\n", encoding="utf-8")

    result = evaluate_scenario(_scenario(), _observation(), repository_root=tmp_path)

    assert result["status"] == "PASS"
    assert result["metrics"]["invariant_recall_rate"] == 1.0
    assert result["execution"] == {
        "s3_commit": "abc123",
        "agent_harness_version": "1",
        "tool_permissions_profile": "standard",
        "task_protocol_version": "agent-memory-v1",
        "repetition": 1,
    }
    assert "must-not-persist" not in json.dumps(result)


def test_oracle_failure_cannot_be_hidden_by_recall(tmp_path: Path) -> None:
    source = tmp_path / "src" / "pkg" / "module.py"
    source.parent.mkdir(parents=True)
    source.write_text("def safe_call():\n    return 'shell=True'\n", encoding="utf-8")

    result = evaluate_scenario(_scenario(), _observation(), repository_root=tmp_path)

    assert result["metrics"]["invariant_recall_rate"] == 1.0
    assert result["status"] == "FAIL"


def test_scenario_discovery_is_deterministic(tmp_path: Path) -> None:
    first = _scenario()
    second = dict(first)
    second["scenario_id"] = "test.memory.v2"
    second["version"] = "2.0.0"
    (tmp_path / "b.json").write_text(json.dumps(second), encoding="utf-8")
    (tmp_path / "a.json").write_text(json.dumps(first), encoding="utf-8")

    rows = list_scenarios(tmp_path)

    assert [row["scenario_id"] for row in rows] == ["test.memory.v1", "test.memory.v2"]


def test_handoff_and_stale_memory_metadata_are_safely_recorded(tmp_path: Path) -> None:
    source = tmp_path / "src" / "pkg" / "module.py"
    source.parent.mkdir(parents=True)
    source.write_text("def safe_call():\n    return 1\n", encoding="utf-8")
    observation = _observation()
    observation["handoff"] = {
        "kind": "cross-agent",
        "source_agent": {
            "provider": "source",
            "model": "a",
            "harness": "one",
            "token": "must-not-persist",
        },
        "target_agent": {"provider": "target", "model": "b", "harness": "two"},
        "transcript_reused": False,
    }
    observation["stale_memory"] = {
        "claim_id": "obsolete-claim",
        "injected": True,
        "secret": "must-not-persist",
    }

    result = evaluate_scenario(_scenario(), observation, repository_root=tmp_path)

    assert result["handoff"] == {
        "kind": "cross-agent",
        "source_agent": {"provider": "source", "model": "a", "harness": "one"},
        "target_agent": {"provider": "target", "model": "b", "harness": "two"},
        "transcript_reused": False,
    }
    assert result["stale_memory"] == {"claim_id": "obsolete-claim", "injected": True}
    assert "must-not-persist" not in json.dumps(result)
