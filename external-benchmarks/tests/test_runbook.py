from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.core import ExternalBenchmarkError, load_scenario  # noqa: E402
from harness.provider_profile import build_provider_profile  # noqa: E402
from harness.runbook import (  # noqa: E402
    build_runbook,
    execute_direct_step,
    handoff_agents_from_runbook,
)
from harness.task_pack import load_task_pack  # noqa: E402
from harness.timeout_policy import TIMEOUT_POLICY_ID, TIMEOUT_SECONDS  # noqa: E402


def _scenarios(*ids: str) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for scenario_id in ids:
        path = EXTERNAL_ROOT / "scenarios" / f"{scenario_id}.json"
        result[scenario_id] = load_scenario(path)
    return result


def _plan(provider_id: str, scenario_rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "campaign_id": "agent-memory-v1",
        "provider": {"id": provider_id, "version": "fixture"},
        "provider_profile": build_provider_profile(provider_id, repository_root=EXTERNAL_ROOT.parent),
        "agent": {"provider": "openai", "model": "fixture-a", "harness": "codex"},
        "execution": {"repetition": 1},
        "scenarios": scenario_rows,
    }


def test_direct_runbook_materializes_prompts_without_absolute_paths(tmp_path: Path) -> None:
    scenario_id = "memory.cross-agent.v1"
    plan = _plan(
        "no-memory",
        [{"scenario_id": scenario_id, "mode": "cross-agent", "worktree_key": "no-memory/run-1/cross-agent"}],
    )
    source_argv = [sys.executable, "-c", "import sys; sys.stdin.read()"]
    target_argv = [sys.executable, "-c", "import sys; sys.stdin.read()", "target"]
    runbook = build_runbook(
        plan,
        scenarios=_scenarios(scenario_id),
        task_pack=load_task_pack(EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json"),
        run_dir=tmp_path,
        direct_argv=source_argv,
        target_agent={"provider": "openai", "model": "fixture-b", "harness": "codex-b"},
        target_direct_argv=target_argv,
    )
    steps = runbook["scenarios"][0]["steps"]
    assert [step["id"] for step in steps] == ["phase-a", "phase-b"]
    assert steps[0]["hard_boundary_after"] is True
    assert steps[1]["agent"]["model"] == "fixture-b"
    assert steps[0]["argv"] != steps[1]["argv"]
    assert runbook["timeout_policy"] == {
        "policy_id": TIMEOUT_POLICY_ID,
        "timeout_seconds": TIMEOUT_SECONDS,
        "on_timeout": "INVALID_OPERATIONAL_RUN",
        "dynamic_adjustment": False,
    }
    payload = json.dumps(runbook)
    assert str(tmp_path) not in payload
    phase_a = (tmp_path / steps[0]["prompt_relpath"]).read_text(encoding="utf-8")
    phase_b = (tmp_path / steps[1]["prompt_relpath"]).read_text(encoding="utf-8")
    assert "cross-agent-balanced-subtraction" in phase_a
    assert "cross-agent-balanced-subtraction" not in phase_b
    assert ".s3-agent-memory-report.json" in phase_b
    assert "reported_invariants" in phase_b

    source, target = handoff_agents_from_runbook(runbook, scenario_id) or ({}, {})
    assert source["model"] == "fixture-a"
    assert target["model"] == "fixture-b"


def test_direct_runbook_rejects_same_target_command(tmp_path: Path) -> None:
    scenario_id = "memory.cross-agent.v1"
    plan = _plan(
        "context-only",
        [{"scenario_id": scenario_id, "mode": "cross-agent", "worktree_key": "context-only/run-1/cross-agent"}],
    )
    argv = [sys.executable, "-c", "pass"]
    with pytest.raises(ExternalBenchmarkError, match="must differ"):
        build_runbook(
            plan,
            scenarios=_scenarios(scenario_id),
            task_pack=load_task_pack(EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json"),
            run_dir=tmp_path,
            direct_argv=argv,
            target_agent={"provider": "openai", "model": "fixture-b", "harness": "codex-b"},
            target_direct_argv=argv,
        )


def test_ai_memory_runbook_uses_provider_isolated_managed_workstream(tmp_path: Path) -> None:
    scenario_id = "memory.checked-i64.v1"
    plan = _plan(
        "ai-memory",
        [{"scenario_id": scenario_id, "mode": "cross-session", "worktree_key": "ai-memory/run-1/checked"}],
    )
    runbook = build_runbook(
        plan,
        scenarios=_scenarios(scenario_id),
        task_pack=load_task_pack(EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json"),
        run_dir=tmp_path,
        target_agent={"provider": "openai", "model": "fixture-b", "harness": "codex-b"},
        ai_memory_executable="ai-memory",
        ai_memory_workspace="s3bench",
        ai_memory_project="s3-agent-memory-v1",
    )
    steps = runbook["scenarios"][0]["steps"]
    assert all(step["runner"] == "ai-memory-managed" for step in steps)
    assert "--new" in steps[0]["argv"]
    assert "--workstream" in steps[1]["argv"]
    assert "--fresh" in steps[0]["argv"] and "--fresh" in steps[1]["argv"]
    source, target = handoff_agents_from_runbook(runbook, scenario_id) or ({}, {})
    assert source == target


def test_single_session_prompt_also_requests_final_agent_report(tmp_path: Path) -> None:
    scenario_id = "memory.host-shell-policy.v1"
    plan = _plan(
        "no-memory",
        [{"scenario_id": scenario_id, "mode": "single-session", "worktree_key": "no-memory/run-1/host"}],
    )
    runbook = build_runbook(
        plan,
        scenarios=_scenarios(scenario_id),
        task_pack=load_task_pack(EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json"),
        run_dir=tmp_path,
        direct_argv=[sys.executable, "-c", "pass"],
        target_agent={"provider": "openai", "model": "fixture-b", "harness": "codex-b"},
        target_direct_argv=[sys.executable, "-c", "pass", "target"],
    )
    step = runbook["scenarios"][0]["steps"][0]
    prompt = (tmp_path / step["prompt_relpath"]).read_text(encoding="utf-8")
    assert ".s3-agent-memory-report.json" in prompt
    assert handoff_agents_from_runbook(runbook, scenario_id) is None


def test_direct_step_executes_prompt_via_stdin(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    worktree_root = tmp_path / "worktrees"
    prompt = run_dir / "prompts/test.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("hello\n", encoding="utf-8")
    worktree = worktree_root / "p/r/s"
    worktree.mkdir(parents=True)
    step = {
        "runner": "direct",
        "argv": [sys.executable, "-c", "import sys; raise SystemExit(0 if sys.stdin.read() == 'hello\\n' else 3)"],
        "prompt_relpath": "prompts/test.md",
        "worktree_key": "p/r/s",
    }
    assert execute_direct_step(step, run_dir=run_dir, worktree_root=worktree_root) == 0
