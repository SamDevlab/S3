"""Provider-neutral execution runbooks for Agent Memory V1."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import ExternalBenchmarkError
from .task_pack import render_phase_prompt, task_for_scenario

RUNBOOK_SCHEMA_VERSION = "1.0.0"
_AI_MEMORY_ARMS = {"ai-memory", "ai-memory+s3-integrity-gate"}
_AGENT_REPORT_NAME = ".s3-agent-memory-report.json"


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalBenchmarkError(f"{name} must be a JSON object")
    return value


def _strings(values: Sequence[str], name: str) -> list[str]:
    result = list(values)
    if not result or any(not isinstance(item, str) or not item for item in result):
        raise ExternalBenchmarkError(f"{name} must be a non-empty argv list")
    return result


def _agent_identity(value: object, name: str) -> dict[str, str]:
    raw = _object(value, name)
    identity: dict[str, str] = {}
    for key in ("provider", "model", "harness"):
        item = raw.get(key)
        if not isinstance(item, str) or not item:
            raise ExternalBenchmarkError(f"{name}.{key} must be a non-empty string")
        identity[key] = item
    return identity


def _prompt_relpath(scenario_id: str, phase: str) -> str:
    suffix = "single" if phase == "single" else f"phase-{phase}"
    return f"prompts/{scenario_id}.{suffix}.md"


def _write_prompt(run_dir: Path, relative: str, content: str) -> None:
    path = run_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _agent_report_instruction() -> str:
    return (
        "\n## Recall report\n\n"
        "After finishing the coding task, write exactly one machine-readable recall sidecar at "
        f"`{_AGENT_REPORT_NAME}` in the worktree root. It is evidence only and must not be used "
        "as a memory/handoff channel. Use exactly this JSON shape and no extra fields:\n\n"
        "```json\n"
        '{"schema_version":"1.0.0","reported_invariants":["invariant-id-you-actually-recall"]}\n'
        "```\n\n"
        "Include only invariant IDs you can state from memory at the end of this phase. "
        "Do not copy a transcript, prompt, repository contents, credentials, or prose into the report. "
        "An empty list is valid when you do not recall an invariant ID.\n"
    )


def handoff_agents_from_runbook(
    runbook: Mapping[str, Any],
    scenario_id: str,
) -> tuple[dict[str, str], dict[str, str]] | None:
    """Derive handoff identities from the actual phase commands recorded in a runbook."""

    rows = runbook.get("scenarios")
    if not isinstance(rows, list):
        raise ExternalBenchmarkError("runbook scenarios are invalid")
    matches = [row for row in rows if isinstance(row, dict) and row.get("scenario_id") == scenario_id]
    if len(matches) != 1:
        raise ExternalBenchmarkError(f"scenario is not uniquely present in runbook: {scenario_id}")
    row = matches[0]
    mode = row.get("mode")
    if mode not in {"cross-session", "cross-agent"}:
        return None
    steps = row.get("steps")
    if not isinstance(steps, list):
        raise ExternalBenchmarkError("runbook scenario steps are invalid")
    phase_a = [step for step in steps if isinstance(step, dict) and step.get("id") == "phase-a"]
    phase_b = [step for step in steps if isinstance(step, dict) and step.get("id") == "phase-b"]
    if len(phase_a) != 1 or len(phase_b) != 1:
        raise ExternalBenchmarkError("runbook handoff requires exactly phase-a and phase-b")
    source = _agent_identity(phase_a[0].get("agent"), "runbook phase-a agent")
    target = _agent_identity(phase_b[0].get("agent"), "runbook phase-b agent")
    if mode == "cross-agent" and source == target:
        raise ExternalBenchmarkError("cross-agent runbook must use distinct agent identities")
    return source, target


def build_runbook(
    plan: Mapping[str, Any],
    *,
    scenarios: Mapping[str, Mapping[str, Any]],
    task_pack: Mapping[str, Any],
    run_dir: Path,
    direct_argv: Sequence[str] = (),
    target_agent: Mapping[str, Any],
    target_direct_argv: Sequence[str] | None = None,
    ai_memory_executable: str = "ai-memory",
    ai_memory_workspace: str = "s3bench",
    ai_memory_project: str = "s3-agent-memory-v1",
    ai_memory_native_args: Sequence[str] = (),
    target_ai_memory_native_args: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Materialize prompts and a safe, path-relative execution runbook."""

    provider = _object(plan.get("provider"), "run plan provider")
    provider_id = provider.get("id")
    if not isinstance(provider_id, str) or not provider_id:
        raise ExternalBenchmarkError("run plan provider.id is invalid")
    profile = _object(plan.get("provider_profile"), "run plan provider_profile")
    source_agent = _agent_identity(plan.get("agent"), "run plan agent")
    clean_target = _agent_identity(target_agent, "target agent")
    if clean_target == source_agent:
        raise ExternalBenchmarkError("target agent identity must differ for cross-agent scenarios")

    managed = provider_id in _AI_MEMORY_ARMS
    if managed:
        direct: list[str] = []
        target_direct: list[str] = []
    else:
        direct = _strings(direct_argv, "direct_argv")
        if target_direct_argv is None:
            raise ExternalBenchmarkError(
                "direct provider arms require explicit target_direct_argv for cross-agent evidence"
            )
        target_direct = _strings(target_direct_argv, "target_direct_argv")
        if target_direct == direct:
            raise ExternalBenchmarkError(
                "cross-agent target_direct_argv must differ from source direct_argv"
            )
    run_dir.mkdir(parents=True, exist_ok=True)

    rows = plan.get("scenarios")
    if not isinstance(rows, list) or not rows:
        raise ExternalBenchmarkError("run plan scenarios are invalid")
    scenario_books: list[dict[str, Any]] = []

    for raw in rows:
        row = _object(raw, "run plan scenario")
        scenario_id = str(row.get("scenario_id", ""))
        mode = str(row.get("mode", ""))
        scenario = scenarios.get(scenario_id)
        if scenario is None:
            raise ExternalBenchmarkError(f"scenario document is missing: {scenario_id}")
        task_for_scenario(task_pack, scenario_id)
        phase_a = render_phase_prompt(task_pack, scenario, profile, phase="a")
        phase_b = render_phase_prompt(task_pack, scenario, profile, phase="b") + _agent_report_instruction()
        worktree_key = row.get("worktree_key")
        if not isinstance(worktree_key, str) or not worktree_key:
            raise ExternalBenchmarkError("run plan worktree_key is invalid")

        steps: list[dict[str, Any]] = []
        if mode == "single-session":
            relpath = _prompt_relpath(scenario_id, "single")
            _write_prompt(run_dir, relpath, phase_a + "\n---\n\n" + phase_b)
            if managed:
                from providers.ai_memory.runner import build_managed_run_command, workstream_name_from_plan

                workstream = workstream_name_from_plan(plan, scenario_id)
                launch = build_managed_run_command(
                    executable=ai_memory_executable,
                    workspace=ai_memory_workspace,
                    project=ai_memory_project,
                    workstream=workstream,
                    phase="new",
                    harness=source_agent["harness"],
                    native_args=ai_memory_native_args,
                    fresh=True,
                )
                argv = list(launch.argv)
                runner = "ai-memory-managed"
            else:
                argv = direct
                runner = "direct"
            steps.append(
                {
                    "id": "single-session",
                    "runner": runner,
                    "argv": argv,
                    "prompt_relpath": relpath,
                    "worktree_key": worktree_key,
                    "hard_boundary_after": False,
                }
            )
        else:
            for phase_name, prompt in (("a", phase_a), ("b", phase_b)):
                relpath = _prompt_relpath(scenario_id, phase_name)
                _write_prompt(run_dir, relpath, prompt)
                receiving = mode == "cross-agent" and phase_name == "b"
                agent = clean_target if receiving else source_agent
                if managed:
                    from providers.ai_memory.runner import build_managed_run_command, workstream_name_from_plan

                    workstream = workstream_name_from_plan(plan, scenario_id)
                    native_args = (
                        target_ai_memory_native_args
                        if receiving and target_ai_memory_native_args is not None
                        else ai_memory_native_args
                    )
                    launch = build_managed_run_command(
                        executable=ai_memory_executable,
                        workspace=ai_memory_workspace,
                        project=ai_memory_project,
                        workstream=workstream,
                        phase="new" if phase_name == "a" else "resume",
                        harness=agent["harness"],
                        native_args=native_args,
                        fresh=True,
                    )
                    argv = list(launch.argv)
                    runner = "ai-memory-managed"
                else:
                    argv = target_direct if receiving else direct
                    runner = "direct"
                steps.append(
                    {
                        "id": f"phase-{phase_name}",
                        "runner": runner,
                        "argv": argv,
                        "prompt_relpath": relpath,
                        "worktree_key": worktree_key,
                        "agent": agent,
                        "hard_boundary_after": phase_name == "a",
                    }
                )
        scenario_books.append({"scenario_id": scenario_id, "mode": mode, "steps": steps})

    document = {
        "schema_version": RUNBOOK_SCHEMA_VERSION,
        "campaign_id": str(plan.get("campaign_id", "")),
        "provider": {"id": provider_id, "version": str(provider.get("version", ""))},
        "provider_profile": profile,
        "source_agent": source_agent,
        "target_agent": clean_target,
        "scenarios": scenario_books,
    }
    (run_dir / "runbook.json").write_text(
        json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return document


def execute_direct_step(
    step: Mapping[str, Any],
    *,
    run_dir: Path,
    worktree_root: Path,
) -> int:
    """Execute only provider-neutral direct steps with prompt content on stdin."""

    if step.get("runner") != "direct":
        raise ExternalBenchmarkError(
            "automatic execution is supported only for direct runbook steps; use the AI-MEMORY adapter for managed steps"
        )
    argv = step.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise ExternalBenchmarkError("runbook direct argv is invalid")
    prompt_relpath = step.get("prompt_relpath")
    worktree_key = step.get("worktree_key")
    if not isinstance(prompt_relpath, str) or not isinstance(worktree_key, str):
        raise ExternalBenchmarkError("runbook step paths are invalid")
    prompt_path = (run_dir / prompt_relpath).resolve()
    worktree = (worktree_root / worktree_key).resolve()
    try:
        prompt_path.relative_to(run_dir.resolve())
        worktree.relative_to(worktree_root.resolve())
    except ValueError as error:
        raise ExternalBenchmarkError("runbook step path escapes its configured root") from error
    if not prompt_path.is_file() or not worktree.is_dir():
        raise ExternalBenchmarkError("runbook prompt or worktree is unavailable")
    try:
        completed = subprocess.run(
            list(argv),
            cwd=worktree,
            input=prompt_path.read_text(encoding="utf-8"),
            text=True,
            shell=False,
            check=False,
        )
    except OSError as error:
        raise ExternalBenchmarkError("direct agent process could not be started") from error
    return int(completed.returncode)
