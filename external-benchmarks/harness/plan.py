"""Deterministic execution-plan generation for external benchmark campaigns."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .core import ExternalBenchmarkError
from .execution import EXECUTION_PROTOCOL_VERSION
from .provider_profile import build_provider_profile
from .timeout_policy import timeout_policy_document

PLAN_SCHEMA_VERSION = "1.1.0"
_TEMPLATE_BY_MODE = {
    "single-session": "single-session.json",
    "cross-session": "cross-session.json",
    "cross-agent": "cross-agent.json",
    "stale-memory": "stale-memory.json",
}


def _required_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ExternalBenchmarkError(f"{name} must be a non-empty string")
    return value


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validate_subject_commit(campaign: Mapping[str, Any], s3_commit: str) -> None:
    protocol = campaign.get("protocol")
    if not isinstance(protocol, dict):
        return
    subject_commit = protocol.get("subject_commit")
    if subject_commit is None:
        return
    expected = _required_string(subject_commit, "campaign protocol.subject_commit")
    if s3_commit != expected:
        raise ExternalBenchmarkError(
            "s3_commit does not match the campaign's pinned subject_commit"
        )


def build_run_plan(
    campaign: Mapping[str, Any],
    *,
    provider_id: str,
    provider_version: str,
    repetition: int,
    s3_commit: str,
    agent_provider: str,
    agent_model: str,
    agent_harness: str,
    agent_harness_version: str,
    tool_permissions_profile: str,
    task_protocol_version: str | None = None,
) -> dict[str, Any]:
    """Build one provider/repetition plan without executing agents or worktrees."""

    allowed_provider_ids = {str(item["id"]) for item in campaign["configurations"]}
    if provider_id not in allowed_provider_ids:
        raise ExternalBenchmarkError(
            f"provider is not a declared campaign configuration: {provider_id}"
        )
    _required_string(provider_version, "provider_version")
    _required_string(s3_commit, "s3_commit")
    _validate_subject_commit(campaign, s3_commit)
    _required_string(agent_provider, "agent_provider")
    _required_string(agent_model, "agent_model")
    _required_string(agent_harness, "agent_harness")
    _required_string(agent_harness_version, "agent_harness_version")
    _required_string(tool_permissions_profile, "tool_permissions_profile")
    if not isinstance(repetition, int) or isinstance(repetition, bool) or repetition < 1:
        raise ExternalBenchmarkError("repetition must be a positive integer")

    protocol_version = task_protocol_version or str(campaign["campaign_id"])
    _required_string(protocol_version, "task_protocol_version")
    template_root = f"templates/{campaign['campaign_id']}"
    run_root = f"{provider_id}/run-{repetition}"

    scenarios: list[dict[str, Any]] = []
    for entry in campaign["scenarios"]:
        scenario_id = str(entry["scenario_id"])
        mode = str(entry["mode"])
        template_name = _TEMPLATE_BY_MODE.get(mode)
        if template_name is None:
            raise ExternalBenchmarkError(f"unsupported plan scenario mode: {mode}")
        required_evidence: list[str] = []
        if mode in {"cross-session", "cross-agent"}:
            required_evidence.append("handoff")
        elif mode == "stale-memory":
            required_evidence.append("stale_memory")

        scenario_plan: dict[str, Any] = {
            "scenario_id": scenario_id,
            "mode": mode,
            "template": f"{template_root}/{template_name}",
            "worktree_key": f"{run_root}/{scenario_id}",
            "observation_path": f"{run_root}/{scenario_id}.observation.json",
            "result_path": f"{run_root}/{scenario_id}.json",
            "required_evidence": required_evidence,
        }
        stale_claim_id = entry.get("stale_claim_id")
        if stale_claim_id is not None:
            scenario_plan["stale_claim_id"] = str(stale_claim_id)
        scenarios.append(scenario_plan)

    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "campaign_id": str(campaign["campaign_id"]),
        "campaign_version": str(campaign["version"]),
        "provider": {"id": provider_id, "version": provider_version},
        "timeout_policy": timeout_policy_document(),
        "provider_profile": build_provider_profile(
            provider_id,
            repository_root=_repository_root(),
        ),
        "agent": {
            "provider": agent_provider,
            "model": agent_model,
            "harness": agent_harness,
        },
        "execution": {
            "s3_commit": s3_commit,
            "agent_harness_version": agent_harness_version,
            "tool_permissions_profile": tool_permissions_profile,
            "task_protocol_version": protocol_version,
            "execution_protocol_version": EXECUTION_PROTOCOL_VERSION,
            "repetition": repetition,
        },
        "run_root": run_root,
        "scenarios": scenarios,
    }
