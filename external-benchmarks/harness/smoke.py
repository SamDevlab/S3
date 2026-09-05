"""Offline structural and semantic smoke validation for Agent Memory V1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .campaign import load_campaign
from .core import ExternalBenchmarkError, evaluate_scenario, load_scenario
from .observation import materialize_observation
from .plan import build_run_plan
from .runbook import build_runbook, handoff_agents_from_runbook
from .task_pack import load_task_pack
from .worktrees import cleanup_worktrees, prepare_worktrees, worktree_plan_document

SMOKE_SCHEMA_VERSION = "1.0.0"
_PROVIDER_VERSIONS = {
    "no-memory": "builtin",
    "context-only": "builtin",
    "ai-memory": "offline-fixture",
    "ai-memory+s3-integrity-gate": "offline-fixture",
}
_SOURCE_AGENT = {"provider": "fixture", "model": "offline-fixture-a", "harness": "codex"}
_TARGET_AGENT = {"provider": "fixture", "model": "offline-fixture-b", "harness": "claude"}


def _scenario_documents(external_root: Path, campaign: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for entry in campaign["scenarios"]:
        scenario_id = str(entry["scenario_id"])
        path = external_root / "scenarios" / f"{scenario_id}.json"
        scenario = load_scenario(path)
        if scenario.get("scenario_id") != scenario_id:
            raise ExternalBenchmarkError(f"smoke scenario id mismatch: {scenario_id}")
        result[scenario_id] = scenario
    return result


def _critical_ids(scenario: dict[str, Any]) -> list[str]:
    values = scenario.get("critical_invariants")
    if not isinstance(values, list):
        raise ExternalBenchmarkError("smoke scenario critical_invariants are invalid")
    result: list[str] = []
    for raw in values:
        if not isinstance(raw, dict):
            raise ExternalBenchmarkError("smoke critical invariant is invalid")
        invariant_id = raw.get("id")
        if not isinstance(invariant_id, str) or not invariant_id:
            raise ExternalBenchmarkError("smoke critical invariant id is invalid")
        result.append(invariant_id)
    return result


def _build_provider_bundle(
    *,
    repository_root: Path,
    external_root: Path,
    workspace_root: Path,
    campaign: dict[str, Any],
    scenarios: dict[str, dict[str, Any]],
    task_pack: dict[str, Any],
    provider_id: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    subject_commit = str(campaign["protocol"]["subject_commit"])
    plan = build_run_plan(
        campaign,
        provider_id=provider_id,
        provider_version=_PROVIDER_VERSIONS[provider_id],
        repetition=1,
        s3_commit=subject_commit,
        agent_provider=_SOURCE_AGENT["provider"],
        agent_model=_SOURCE_AGENT["model"],
        agent_harness=_SOURCE_AGENT["harness"],
        agent_harness_version="offline-fixture-1",
        tool_permissions_profile="offline-protocol-smoke",
        task_protocol_version="agent-memory-v1",
    )
    run_dir = workspace_root / provider_id / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    runbook = build_runbook(
        plan,
        scenarios=scenarios,
        task_pack=task_pack,
        run_dir=run_dir,
        direct_argv=["fixture-agent-a"],
        target_agent=_TARGET_AGENT,
        target_direct_argv=["fixture-agent-b"],
        ai_memory_executable="ai-memory",
        ai_memory_workspace="s3bench",
        ai_memory_project="s3-agent-memory-v1",
    )
    preview = worktree_plan_document(
        plan,
        repository_root=repository_root,
        worktree_root=workspace_root / "worktree-preview" / provider_id,
    )
    if len(preview["worktrees"]) != len(campaign["scenarios"]):
        raise ExternalBenchmarkError("smoke worktree plan is incomplete")

    observations: list[dict[str, Any]] = []
    for entry in campaign["scenarios"]:
        scenario_id = str(entry["scenario_id"])
        handoff = handoff_agents_from_runbook(runbook, scenario_id)
        source = handoff[0] if handoff is not None else None
        target = handoff[1] if handoff is not None else None
        observation = materialize_observation(
            plan,
            scenario_id=scenario_id,
            reported_invariants=_critical_ids(scenarios[scenario_id]),
            source_agent=source,
            target_agent=target,
            process_metadata=[
                {
                    "phase": str(step["id"]),
                    "agent": dict(step.get("agent", plan["agent"])),
                    "runner": str(step["runner"]),
                    "returncode": 0,
                    "timed_out": False,
                    "elapsed_seconds": 0.0,
                }
                for step in runbook["scenarios"]
                if isinstance(step, dict)
                and step.get("scenario_id") == scenario_id
                for step in step["steps"]
            ],
        )
        if observation["provider"]["id"] != provider_id:
            raise ExternalBenchmarkError("smoke observation provider mismatch")
        if observation["execution"]["s3_commit"] != subject_commit:
            raise ExternalBenchmarkError("smoke observation subject commit mismatch")
        if entry["mode"] in {"cross-session", "cross-agent"}:
            evidence = observation.get("handoff")
            if not isinstance(evidence, dict) or evidence.get("transcript_reused") is not False:
                raise ExternalBenchmarkError("smoke handoff evidence is invalid")
        observations.append(observation)
    return plan, runbook, observations


def run_protocol_smoke(
    *,
    repository_root: Path,
    workspace_root: Path,
    with_oracles: bool = False,
) -> dict[str, Any]:
    """Validate all 28 provider/scenario bundles without making provider capability claims."""

    repository_root = repository_root.resolve()
    external_root = repository_root / "external-benchmarks"
    campaign = load_campaign(external_root / "campaigns" / "agent-memory-v1.json")
    task_pack = load_task_pack(external_root / "task-packs" / "agent-memory-v1.json")
    scenarios = _scenario_documents(external_root, campaign)
    providers = [str(item["id"]) for item in campaign["configurations"]]
    if providers != list(_PROVIDER_VERSIONS):
        raise ExternalBenchmarkError("Agent Memory V1 provider set differs from smoke protocol")

    workspace_root = workspace_root.resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    provider_bundles: dict[str, tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]] = {}
    bundles = 0
    steps = 0
    for provider_id in providers:
        plan, runbook, observations = _build_provider_bundle(
            repository_root=repository_root,
            external_root=external_root,
            workspace_root=workspace_root,
            campaign=campaign,
            scenarios=scenarios,
            task_pack=task_pack,
            provider_id=provider_id,
        )
        provider_bundles[provider_id] = (plan, runbook, observations)
        bundles += len(observations)
        runbook_rows = runbook.get("scenarios")
        if not isinstance(runbook_rows, list):
            raise ExternalBenchmarkError("smoke runbook scenarios are invalid")
        for row in runbook_rows:
            if not isinstance(row, dict) or not isinstance(row.get("steps"), list):
                raise ExternalBenchmarkError("smoke runbook step structure is invalid")
            steps += len(row["steps"])

    expected_bundles = len(providers) * len(campaign["scenarios"])
    if bundles != expected_bundles or expected_bundles != 28:
        raise ExternalBenchmarkError("Agent Memory V1 smoke must contain exactly 28 bundles")
    if steps != 52:
        raise ExternalBenchmarkError("Agent Memory V1 smoke must contain exactly 52 phase steps")

    semantic_failures: list[str] = []
    semantic_validated = 0
    if with_oracles:
        plan, runbook, observations = provider_bundles["no-memory"]
        worktree_root = workspace_root / "semantic-oracle-worktrees"
        specs = prepare_worktrees(
            plan,
            repository_root=repository_root,
            worktree_root=worktree_root,
        )
        by_scenario = {spec.scenario_id: spec.path for spec in specs}
        try:
            for entry, observation in zip(campaign["scenarios"], observations, strict=True):
                scenario_id = str(entry["scenario_id"])
                result = evaluate_scenario(
                    scenarios[scenario_id],
                    observation,
                    repository_root=by_scenario[scenario_id],
                )
                semantic_validated += 1
                if result["status"] not in {"PASS", "VALID_PASS"}:
                    semantic_failures.append(scenario_id)
        finally:
            cleanup_worktrees(
                repository_root=repository_root,
                worktree_root=worktree_root,
                discard_changes=True,
            )

    passed = not semantic_failures
    return {
        "schema_version": SMOKE_SCHEMA_VERSION,
        "kind": "protocol-smoke",
        "status": "PASS" if passed else "FAIL",
        "scientific_claims_allowed": False,
        "subject_commit": str(campaign["protocol"]["subject_commit"]),
        "providers": len(providers),
        "scenarios": len(campaign["scenarios"]),
        "bundles": bundles,
        "phase_steps": steps,
        "synthetic_observations": bundles,
        "semantic_oracles_validated": semantic_validated,
        "semantic_oracle_failures": sorted(semantic_failures),
    }
