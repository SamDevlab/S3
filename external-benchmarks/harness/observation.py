"""Deterministic observation materialization from external benchmark run plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import ExternalBenchmarkError
from .execution import (
    EXECUTION_PROTOCOL_VERSION,
    ExecutionEvidenceError,
    classify_process_phases,
    load_process_metadata,
)


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalBenchmarkError(f"{name} must be a JSON object")
    return value


def _agent(value: object, name: str) -> dict[str, str]:
    raw = _object(value, name)
    result: dict[str, str] = {}
    for key in ("provider", "model", "harness"):
        item = raw.get(key)
        if not isinstance(item, str) or not item:
            raise ExternalBenchmarkError(f"{name}.{key} must be a non-empty string")
        result[key] = item
    return result


def _scenario(plan: Mapping[str, Any], scenario_id: str) -> dict[str, Any]:
    rows = plan.get("scenarios")
    if not isinstance(rows, list):
        raise ExternalBenchmarkError("run plan scenarios must be a list")
    matches = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("scenario_id") == scenario_id
    ]
    if len(matches) != 1:
        raise ExternalBenchmarkError(
            f"scenario is not uniquely present in run plan: {scenario_id}"
        )
    return matches[0]


def materialize_observation(
    plan: Mapping[str, Any],
    *,
    scenario_id: str,
    reported_invariants: Sequence[str] = (),
    source_agent: Mapping[str, Any] | None = None,
    target_agent: Mapping[str, Any] | None = None,
    process_metadata_dir: Path | None = None,
    process_metadata: Sequence[Mapping[str, Any]] | None = None,
    runbook: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create safe scenario observation metadata from one pinned run plan."""

    provider = _object(plan.get("provider"), "run plan provider")
    provider_id = provider.get("id")
    provider_version = provider.get("version")
    if not isinstance(provider_id, str) or not provider_id:
        raise ExternalBenchmarkError("run plan provider.id is invalid")
    if not isinstance(provider_version, str) or not provider_version:
        raise ExternalBenchmarkError("run plan provider.version is invalid")

    agent = _agent(plan.get("agent"), "run plan agent")
    execution = _object(plan.get("execution"), "run plan execution")
    clean_execution: dict[str, Any] = {}
    for key in (
        "s3_commit",
        "agent_harness_version",
        "tool_permissions_profile",
        "task_protocol_version",
    ):
        item = execution.get(key)
        if not isinstance(item, str) or not item:
            raise ExternalBenchmarkError(f"run plan execution.{key} is invalid")
        clean_execution[key] = item
    repetition = execution.get("repetition")
    if not isinstance(repetition, int) or isinstance(repetition, bool) or repetition < 1:
        raise ExternalBenchmarkError("run plan execution.repetition is invalid")
    clean_execution["repetition"] = repetition
    execution_protocol_version = execution.get("execution_protocol_version")
    if execution_protocol_version is not None:
        if not isinstance(execution_protocol_version, str) or not execution_protocol_version:
            raise ExternalBenchmarkError("run plan execution.execution_protocol_version is invalid")
        clean_execution["execution_protocol_version"] = execution_protocol_version

    if any(not isinstance(item, str) or not item for item in reported_invariants):
        raise ExternalBenchmarkError("reported invariants must be non-empty strings")
    scenario = _scenario(plan, scenario_id)
    mode = scenario.get("mode")
    if mode not in {"single-session", "cross-session", "cross-agent", "stale-memory"}:
        raise ExternalBenchmarkError(f"unsupported observation scenario mode: {mode}")

    observation: dict[str, Any] = {
        "provider": {"id": provider_id, "version": provider_version},
        "agent": agent,
        "execution": clean_execution,
        "reported_invariants": sorted(set(reported_invariants)),
    }

    if execution_protocol_version == EXECUTION_PROTOCOL_VERSION:
        try:
            if process_metadata_dir is not None:
                phases = load_process_metadata(
                    runbook if runbook is not None else _runbook_for_observation(plan),
                    scenario_id=scenario_id,
                    directory=process_metadata_dir,
                )
            elif process_metadata is not None:
                phases = [dict(item) for item in process_metadata]
            else:
                raise ExecutionEvidenceError("required process metadata was not supplied")
            observation["agent_process"] = classify_process_phases(phases)
        except (ExecutionEvidenceError, KeyError, TypeError, ValueError) as error:
            observation["agent_process"] = {
                "status": "INVALID_EXECUTION_EVIDENCE",
                "phases": [],
                "required_processes": 0,
                "nonzero_exits": [],
                "timeouts": [],
                "reason": str(error),
            }

    if mode == "cross-session":
        source_value: object = agent if source_agent is None else source_agent
        target_value: object = agent if target_agent is None else target_agent
        source = _agent(source_value, "source agent")
        target = _agent(target_value, "target agent")
        observation["handoff"] = {
            "kind": "cross-session",
            "source_agent": source,
            "target_agent": target,
            "transcript_reused": False,
        }
    elif mode == "cross-agent":
        if source_agent is None or target_agent is None:
            raise ExternalBenchmarkError(
                "cross-agent observation requires source and target agent identities"
            )
        source = _agent(source_agent, "source agent")
        target = _agent(target_agent, "target agent")
        if source == target:
            raise ExternalBenchmarkError(
                "cross-agent observation requires distinct source and target identities"
            )
        observation["handoff"] = {
            "kind": "cross-agent",
            "source_agent": source,
            "target_agent": target,
            "transcript_reused": False,
        }
    elif mode == "stale-memory":
        claim_id = scenario.get("stale_claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise ExternalBenchmarkError("stale-memory run plan is missing stale_claim_id")
        observation["stale_memory"] = {
            "claim_id": claim_id,
            "injected": True,
        }

    return observation


def _runbook_for_observation(plan: Mapping[str, Any]) -> Mapping[str, Any]:
    """Extract the runbook only when a caller explicitly attached it to a plan."""

    runbook = plan.get("runbook")
    if not isinstance(runbook, dict):
        raise ExecutionEvidenceError(
            "process metadata directory requires the runbook structure in the plan"
        )
    return runbook
