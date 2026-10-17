from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_observation_cli_uses_agent_report_and_runbook_handoff(tmp_path: Path) -> None:
    plan = {
        "provider": {"id": "no-memory", "version": "fixture"},
        "agent": {"provider": "openai", "model": "source", "harness": "codex-a"},
        "execution": {
            "s3_commit": "a" * 40,
            "agent_harness_version": "1",
            "tool_permissions_profile": "standard",
            "task_protocol_version": "agent-memory-v1",
            "repetition": 1,
        },
        "scenarios": [
            {
                "scenario_id": "memory.cross-agent.v1",
                "mode": "cross-agent",
                "worktree_key": "no-memory/run-1/cross-agent",
            }
        ],
    }
    runbook = {
        "scenarios": [
            {
                "scenario_id": "memory.cross-agent.v1",
                "mode": "cross-agent",
                "steps": [
                    {
                        "id": "phase-a",
                        "agent": {"provider": "openai", "model": "source", "harness": "codex-a"},
                    },
                    {
                        "id": "phase-b",
                        "agent": {"provider": "openai", "model": "target", "harness": "codex-b"},
                    },
                ],
            }
        ]
    }
    report = {
        "schema_version": "1.0.0",
        "reported_invariants": ["cross-agent-i64-checked"],
    }
    plan_path = tmp_path / "plan.json"
    runbook_path = tmp_path / "runbook.json"
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "observation.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    runbook_path.write_text(json.dumps(runbook), encoding="utf-8")
    report_path.write_text(json.dumps(report), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "tools" / "external_bench_observation.py"),
            "--plan-file",
            str(plan_path),
            "--scenario",
            "memory.cross-agent.v1",
            "--agent-report-file",
            str(report_path),
            "--runbook-file",
            str(runbook_path),
            "--output-json",
            str(output_path),
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    observation = json.loads(output_path.read_text(encoding="utf-8"))
    assert observation["reported_invariants"] == ["cross-agent-i64-checked"]
    assert observation["handoff"]["source_agent"]["model"] == "source"
    assert observation["handoff"]["target_agent"]["model"] == "target"
    assert observation["handoff"]["transcript_reused"] is False
