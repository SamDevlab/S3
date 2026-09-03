"""Campaign aggregation for repository-only external benchmarks."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Mapping

from .core import ExternalBenchmarkError, SCHEMA_VERSION as SCENARIO_RESULT_SCHEMA_VERSION

CAMPAIGN_SCHEMA_VERSION = "1.0.0"
CAMPAIGN_RESULT_SCHEMA_VERSION = "1.0.0"
_ALLOWED_MODES = {"single-session", "cross-session", "cross-agent", "stale-memory"}


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
        if not isinstance(configuration_id, str) or not configuration_id:
            raise ExternalBenchmarkError("campaign configuration id must be a non-empty string")
        configuration_ids.append(configuration_id)
    if len(configuration_ids) != len(set(configuration_ids)):
        raise ExternalBenchmarkError("campaign configuration ids must be unique")

    scenarios = document["scenarios"]
    if not isinstance(scenarios, list) or not scenarios:
        raise ExternalBenchmarkError("campaign scenarios must be a non-empty list")
    scenario_ids: list[str] = []
    for item in scenarios:
        scenario = _require_object(item, "campaign scenario")
        scenario_id = scenario.get("scenario_id")
        mode = scenario.get("mode")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise ExternalBenchmarkError("campaign scenario_id must be a non-empty string")
        if mode not in _ALLOWED_MODES:
            raise ExternalBenchmarkError(f"unsupported campaign scenario mode: {mode}")
        scenario_ids.append(scenario_id)
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ExternalBenchmarkError("campaign scenario ids must be unique")

    _require_object(document["protocol"], "campaign protocol")
    _require_object(document["gates"], "campaign gates")
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
    _require_object(document.get("metrics"), "scenario result metrics")
    return document


def _agent_identity(value: object, name: str) -> tuple[str, str, str]:
    agent = _require_object(value, name)
    return (
        str(agent.get("provider", "")),
        str(agent.get("model", "")),
        str(agent.get("harness", "")),
    )


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
            raise ExternalBenchmarkError(f"cross-agent scenario requires distinct agent identities: {scenario_id}")
    elif mode == "stale-memory":
        stale = _require_object(result.get("stale_memory"), f"stale-memory evidence for {scenario_id}")
        if stale.get("injected") is not True:
            raise ExternalBenchmarkError(f"stale memory was not recorded as injected for {scenario_id}")


def aggregate_campaign(campaign: Mapping[str, Any], *, result_dir: Path) -> dict[str, Any]:
    result_dir = result_dir.resolve()
    if not result_dir.is_dir():
        raise ExternalBenchmarkError("campaign result directory does not exist")

    allowed_provider_ids = {
        str(_require_object(item, "campaign configuration")["id"])
        for item in campaign["configurations"]
    }
    results: list[dict[str, Any]] = []
    provider_keys: set[tuple[str, str]] = set()
    for entry in campaign["scenarios"]:
        scenario_id = str(entry["scenario_id"])
        result = _load_scenario_result(result_dir / f"{scenario_id}.json", scenario_id)
        _validate_protocol_evidence(entry, result)
        provider = result["provider"]
        provider_id = str(provider["id"])
        if provider_id not in allowed_provider_ids:
            raise ExternalBenchmarkError(f"provider is not a declared campaign configuration: {provider_id}")
        result = dict(result)
        result["campaign_mode"] = str(entry["mode"])
        results.append(result)
        provider_keys.add((provider_id, str(provider.get("version", "unknown"))))

    gates = _require_object(campaign["gates"], "campaign gates")
    if gates.get("provider_consistency", True) and len(provider_keys) != 1:
        raise ExternalBenchmarkError("campaign results must use one provider configuration per aggregation")

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

    require_all = bool(gates.get("require_all_oracles_pass", True))
    status = "FAIL" if require_all and failed else "PASS"
    provider_id, provider_version = next(iter(provider_keys)) if provider_keys else ("unknown", "unknown")
    mean_recall = statistics.fmean(recalls) if recalls else None

    return {
        "schema_version": CAMPAIGN_RESULT_SCHEMA_VERSION,
        "campaign_id": str(campaign["campaign_id"]),
        "campaign_version": str(campaign["version"]),
        "category": str(campaign["category"]),
        "provider": {"id": provider_id, "version": provider_version},
        "status": status,
        "metrics": {
            "scenarios_total": len(results),
            "scenarios_passed": passed,
            "scenarios_failed": failed,
            "critical_oracle_failures": critical_oracle_failures,
            "mean_invariant_recall_rate": mean_recall,
        },
        "results": results,
    }
