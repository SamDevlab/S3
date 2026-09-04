"""Campaign aggregation for repository-only external benchmarks."""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Any, Mapping

from .core import ExternalBenchmarkError, SCHEMA_VERSION as SCENARIO_RESULT_SCHEMA_VERSION

CAMPAIGN_SCHEMA_VERSION = "1.0.0"
CAMPAIGN_RESULT_SCHEMA_VERSION = "1.0.0"
_ALLOWED_MODES = {"single-session", "cross-session", "cross-agent", "stale-memory"}
_SAFE_ID = re.compile(r"^[A-Za-z0-9._+-]+$")
_EXECUTION_KEYS = (
    "s3_commit",
    "agent_harness_version",
    "tool_permissions_profile",
    "task_protocol_version",
    "repetition",
)


def _require_object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalBenchmarkError(f"{name} must be a JSON object")
    return value


def load_campaign(path: Path) -> dict[str, Any]:
    document = _require_object(json.loads(path.read_text(encoding="utf-8")), "campaign")
    required = {
        "schema_version",
        "campaign_id",
        "version",
        "category",
        "objective",
        "configurations",
        "protocol",
        "scenarios",
        "gates",
    }
    missing = sorted(required.difference(document))
    if missing:
        raise ExternalBenchmarkError(f"campaign missing required fields: {', '.join(missing)}")
    if document["schema_version"] != CAMPAIGN_SCHEMA_VERSION:
        raise ExternalBenchmarkError("unsupported external benchmark campaign schema")

    configurations = document["configurations"]
    if not isinstance(configurations, list) or not configurations:
        raise ExternalBenchmarkError("campaign configurations must be a non-empty list")
    configuration_ids: list[str] = []
    for item in configurations:
        configuration = _require_object(item, "campaign configuration")
        configuration_id = configuration.get("id")
        description = configuration.get("description")
        if not isinstance(configuration_id, str) or not _SAFE_ID.fullmatch(configuration_id):
            raise ExternalBenchmarkError("campaign configuration id must be a safe non-empty id")
        if not isinstance(description, str) or not description:
            raise ExternalBenchmarkError("campaign configuration description must be a non-empty string")
        configuration_ids.append(configuration_id)
    if len(configuration_ids) != len(set(configuration_ids)):
        raise ExternalBenchmarkError("campaign configuration ids must be unique")

    protocol = _require_object(document["protocol"], "campaign protocol")
    if protocol.get("worktree_isolation") != "fresh-worktree-per-scenario":
        raise ExternalBenchmarkError("campaign worktree isolation must be fresh-worktree-per-scenario")
    repetitions = protocol.get("recommended_repetitions")
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 1:
        raise ExternalBenchmarkError("campaign recommended_repetitions must be a positive integer")
    result_collection = protocol.get("result_collection")
    rules = protocol.get("rules")
    if not isinstance(result_collection, str) or not result_collection:
        raise ExternalBenchmarkError("campaign result_collection must be a non-empty string")
    if (
        not isinstance(rules, list)
        or not rules
        or any(not isinstance(rule, str) or not rule for rule in rules)
    ):
        raise ExternalBenchmarkError("campaign rules must be a non-empty string list")

    scenarios = document["scenarios"]
    if not isinstance(scenarios, list) or not scenarios:
        raise ExternalBenchmarkError("campaign scenarios must be a non-empty list")
    scenario_ids: list[str] = []
    for item in scenarios:
        scenario = _require_object(item, "campaign scenario")
        scenario_id = scenario.get("scenario_id")
        mode = scenario.get("mode")
        purpose = scenario.get("purpose")
        if not isinstance(scenario_id, str) or not _SAFE_ID.fullmatch(scenario_id):
            raise ExternalBenchmarkError("campaign scenario_id must be a safe non-empty id")
        if mode not in _ALLOWED_MODES:
            raise ExternalBenchmarkError(f"unsupported campaign scenario mode: {mode}")
        if not isinstance(purpose, str) or not purpose:
            raise ExternalBenchmarkError("campaign scenario purpose must be a non-empty string")
        stale_claim_id = scenario.get("stale_claim_id")
        if mode == "stale-memory":
            if not isinstance(stale_claim_id, str) or not _SAFE_ID.fullmatch(stale_claim_id):
                raise ExternalBenchmarkError(
                    "stale-memory campaign scenario requires a safe stale_claim_id"
                )
        elif stale_claim_id is not None:
            raise ExternalBenchmarkError("stale_claim_id is valid only for stale-memory scenarios")
        scenario_ids.append(scenario_id)
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ExternalBenchmarkError("campaign scenario ids must be unique")

    expected_gates = {
        "require_all_oracles_pass": True,
        "recall_is_gate": False,
        "provider_consistency": True,
    }
    if _require_object(document["gates"], "campaign gates") != expected_gates:
        raise ExternalBenchmarkError(
            "campaign 1.0.0 requires correctness-first, non-recall, single-provider gates"
        )
    return document


def list_campaigns(root: Path) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    for path in sorted(root.glob("*.json")):
        campaign = load_campaign(path)
        rows.append(
            {
                "campaign_id": str(campaign["campaign_id"]),
                "version": str(campaign["version"]),
                "category": str(campaign["category"]),
                "scenarios": len(campaign["scenarios"]),
                "objective": str(campaign["objective"]),
            }
        )
    return rows


def _load_scenario_result(path: Path, expected_scenario_id: str) -> dict[str, Any]:
    try:
        document = _require_object(json.loads(path.read_text(encoding="utf-8")), "scenario result")
    except OSError as error:
        raise ExternalBenchmarkError(f"missing scenario result: {path.name}") from error
    except json.JSONDecodeError as error:
        raise ExternalBenchmarkError(f"invalid scenario result JSON: {path.name}") from error

    if document.get("schema_version") != SCENARIO_RESULT_SCHEMA_VERSION:
        raise ExternalBenchmarkError(f"unsupported scenario result schema: {path.name}")
    if document.get("scenario_id") != expected_scenario_id:
        raise ExternalBenchmarkError(
            f"scenario result id mismatch for {path.name}: expected {expected_scenario_id}"
        )
    if document.get("status") not in {"PASS", "FAIL"}:
        raise ExternalBenchmarkError(f"invalid scenario result status: {path.name}")
    provider = _require_object(document.get("provider"), "scenario result provider")
    if not isinstance(provider.get("id"), str) or not provider["id"]:
        raise ExternalBenchmarkError(f"scenario result provider id is invalid: {path.name}")
    if not isinstance(provider.get("version"), str) or not provider["version"]:
        raise ExternalBenchmarkError(f"scenario result provider version is invalid: {path.name}")
    _require_object(document.get("metrics"), "scenario result metrics")
    return document


def _agent_identity(value: object, name: str) -> tuple[str, str, str]:
    agent = _require_object(value, name)
    identity = (
        str(agent.get("provider", "")),
        str(agent.get("model", "")),
        str(agent.get("harness", "")),
    )
    if not any(identity):
        raise ExternalBenchmarkError(f"{name} must contain at least one identity field")
    return identity


def _execution_identity(value: object, scenario_id: str) -> tuple[object, ...]:
    execution = _require_object(value, f"execution metadata for {scenario_id}")
    identity: list[object] = []
    for key in _EXECUTION_KEYS:
        item = execution.get(key)
        if key == "repetition":
            if not isinstance(item, int) or isinstance(item, bool) or item < 1:
                raise ExternalBenchmarkError(f"execution repetition is invalid for {scenario_id}")
        elif not isinstance(item, str) or not item:
            raise ExternalBenchmarkError(f"execution {key} is invalid for {scenario_id}")
        identity.append(item)
    return tuple(identity)


def _validate_protocol_evidence(entry: Mapping[str, Any], result: Mapping[str, Any]) -> None:
    mode = str(entry["mode"])
    scenario_id = str(entry["scenario_id"])
    if mode in {"cross-session", "cross-agent"}:
        handoff = _require_object(result.get("handoff"), f"handoff evidence for {scenario_id}")
        if handoff.get("kind") != mode:
            raise ExternalBenchmarkError(f"handoff kind mismatch for {scenario_id}")
        if handoff.get("transcript_reused") is not False:
            raise ExternalBenchmarkError(f"transcript reuse is forbidden for {scenario_id}")
        source = _agent_identity(handoff.get("source_agent"), f"source agent for {scenario_id}")
        target = _agent_identity(handoff.get("target_agent"), f"target agent for {scenario_id}")
        if mode == "cross-agent" and source == target:
            raise ExternalBenchmarkError(
                f"cross-agent scenario requires distinct agent identities: {scenario_id}"
            )
    elif mode == "stale-memory":
        stale = _require_object(result.get("stale_memory"), f"stale-memory evidence for {scenario_id}")
        claim_id = stale.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise ExternalBenchmarkError(f"stale-memory claim id is missing for {scenario_id}")
        if claim_id != entry.get("stale_claim_id"):
            raise ExternalBenchmarkError(f"stale-memory claim id mismatch for {scenario_id}")
        if stale.get("injected") is not True:
            raise ExternalBenchmarkError(
                f"stale memory was not recorded as injected for {scenario_id}"
            )


def aggregate_campaign(campaign: Mapping[str, Any], *, result_dir: Path) -> dict[str, Any]:
    result_dir = result_dir.resolve()
    if not result_dir.is_dir():
        raise ExternalBenchmarkError("campaign result directory does not exist")

    allowed_provider_ids = {
        str(_require_object(item, "campaign configuration").get("id", ""))
        for item in campaign["configurations"]
    }
    results: list[dict[str, Any]] = []
    provider_keys: set[tuple[str, str]] = set()
    execution_keys: set[tuple[object, ...]] = set()
    for entry in campaign["scenarios"]:
        scenario_id = str(entry["scenario_id"])
        result = _load_scenario_result(result_dir / f"{scenario_id}.json", scenario_id)
        _validate_protocol_evidence(entry, result)
        provider = result["provider"]
        provider_id = str(provider["id"])
        if provider_id not in allowed_provider_ids:
            raise ExternalBenchmarkError(
                f"provider is not a declared campaign configuration: {provider_id}"
            )
        execution_keys.add(_execution_identity(result.get("execution"), scenario_id))
        result = dict(result)
        result["campaign_mode"] = str(entry["mode"])
        results.append(result)
        provider_keys.add((provider_id, str(provider["version"])))

    if len(provider_keys) != 1:
        raise ExternalBenchmarkError(
            "campaign results must use one provider configuration per aggregation"
        )
    if len(execution_keys) != 1:
        raise ExternalBenchmarkError(
            "campaign results must share one execution profile and repetition"
        )

    passed = sum(1 for result in results if result["status"] == "PASS")
    failed = len(results) - passed
    recalls: list[float] = []
    critical_oracle_failures = 0
    for result in results:
        metrics = result["metrics"]
        recall = metrics.get("invariant_recall_rate")
        if isinstance(recall, (int, float)):
            recalls.append(float(recall))
        failures = metrics.get("critical_oracle_failures", 0)
        if isinstance(failures, int):
            critical_oracle_failures += failures

    provider_id, provider_version = next(iter(provider_keys))
    execution = dict(zip(_EXECUTION_KEYS, next(iter(execution_keys)), strict=True))
    return {
        "schema_version": CAMPAIGN_RESULT_SCHEMA_VERSION,
        "campaign_id": str(campaign["campaign_id"]),
        "campaign_version": str(campaign["version"]),
        "category": str(campaign["category"]),
        "provider": {"id": provider_id, "version": provider_version},
        "execution": execution,
        "status": "FAIL" if failed else "PASS",
        "metrics": {
            "scenarios_total": len(results),
            "scenarios_passed": passed,
            "scenarios_failed": failed,
            "critical_oracle_failures": critical_oracle_failures,
            "mean_invariant_recall_rate": statistics.fmean(recalls) if recalls else None,
        },
        "results": results,
    }
