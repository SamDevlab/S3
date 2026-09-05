"""Cross-provider comparison for versioned external benchmark campaigns."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Mapping

from .campaign import CAMPAIGN_RESULT_SCHEMA_VERSION, LEGACY_CAMPAIGN_RESULT_SCHEMA_VERSION
from .core import ExternalBenchmarkError
from .execution import RESULT_SCHEMA_VERSION, VALID_RESULT_STATUSES
from .plan import PLAN_SCHEMA_VERSION
from .provider_profile import provider_profile_identity, sanitize_provider_profile
from .timeout_policy import timeout_policy_document

COMPARISON_SCHEMA_VERSION = "1.0.0"
_COMPARABILITY_KEYS = (
    "s3_commit",
    "agent_harness_version",
    "tool_permissions_profile",
    "task_protocol_version",
    "execution_protocol_version",
)
_LEGACY_EXECUTION_PROTOCOL = "legacy-agent-memory-v1.0.0"
_PLAN_SCHEMA_VERSIONS = {"1.0.0", PLAN_SCHEMA_VERSION}
_CAMPAIGN_RESULT_SCHEMA_VERSIONS = {
    LEGACY_CAMPAIGN_RESULT_SCHEMA_VERSION,
    CAMPAIGN_RESULT_SCHEMA_VERSION,
}


def _require_object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalBenchmarkError(f"{name} must be a JSON object")
    return value


def _read_object(path: Path, name: str) -> dict[str, Any]:
    try:
        return _require_object(json.loads(path.read_text(encoding="utf-8")), name)
    except OSError as error:
        raise ExternalBenchmarkError(f"missing {name}: {path}") from error
    except json.JSONDecodeError as error:
        raise ExternalBenchmarkError(f"invalid {name} JSON: {path}") from error


def _load_campaign_result(path: Path) -> dict[str, Any]:
    document = _read_object(path, "campaign result")
    if document.get("schema_version") not in _CAMPAIGN_RESULT_SCHEMA_VERSIONS:
        raise ExternalBenchmarkError(f"unsupported campaign result schema: {path}")
    if document.get("status") not in {"PASS", "FAIL"}:
        raise ExternalBenchmarkError(f"invalid campaign result status: {path}")
    provider = _require_object(document.get("provider"), "campaign result provider")
    for key in ("id", "version"):
        value = provider.get(key)
        if not isinstance(value, str) or not value:
            raise ExternalBenchmarkError(f"campaign result provider.{key} is invalid: {path}")
    execution = _require_object(document.get("execution"), "campaign result execution")
    for key in _COMPARABILITY_KEYS:
        value = execution.get(key)
        if key == "execution_protocol_version" and value is None:
            continue
        if not isinstance(value, str) or not value:
            raise ExternalBenchmarkError(f"campaign result execution.{key} is invalid: {path}")
    repetition = execution.get("repetition")
    if not isinstance(repetition, int) or isinstance(repetition, bool) or repetition < 1:
        raise ExternalBenchmarkError(f"campaign result execution.repetition is invalid: {path}")
    if not isinstance(document.get("results"), list):
        raise ExternalBenchmarkError(f"campaign result results must be a list: {path}")
    return document


def _load_run_plan(
    path: Path,
    *,
    campaign: Mapping[str, Any],
    provider_id: str,
    repetition: int,
) -> dict[str, Any]:
    plan = _read_object(path, "run plan")
    if plan.get("schema_version") not in _PLAN_SCHEMA_VERSIONS:
        raise ExternalBenchmarkError(f"unsupported run plan schema: {path}")
    if plan.get("campaign_id") != campaign["campaign_id"]:
        raise ExternalBenchmarkError(f"run plan campaign id mismatch: {path}")
    if plan.get("campaign_version") != campaign["version"]:
        raise ExternalBenchmarkError(f"run plan campaign version mismatch: {path}")
    provider = _require_object(plan.get("provider"), "run plan provider")
    if provider.get("id") != provider_id:
        raise ExternalBenchmarkError(f"run plan provider id mismatch: {path}")
    if not isinstance(provider.get("version"), str) or not provider["version"]:
        raise ExternalBenchmarkError(f"run plan provider version is invalid: {path}")
    execution = _require_object(plan.get("execution"), "run plan execution")
    if execution.get("repetition") != repetition:
        raise ExternalBenchmarkError(f"run plan repetition mismatch: {path}")
    if plan.get("timeout_policy") != timeout_policy_document():
        raise ExternalBenchmarkError(f"run plan timeout policy is not frozen v1: {path}")
    plan["provider_profile"] = sanitize_provider_profile(
        plan.get("provider_profile"),
        provider_id=provider_id,
    )
    return plan


def _validate_plan_result_pair(
    plan: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    path: Path,
) -> None:
    if _require_object(plan["provider"], "run plan provider") != _require_object(
        result["provider"], "campaign result provider"
    ):
        raise ExternalBenchmarkError(f"run plan provider differs from campaign result: {path}")
    if _require_object(plan["execution"], "run plan execution") != _require_object(
        result["execution"], "campaign result execution"
    ):
        raise ExternalBenchmarkError(f"run plan execution differs from campaign result: {path}")


def _scenario_map(result: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}
    for item in result["results"]:
        scenario = _require_object(item, "scenario result")
        scenario_id = scenario.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise ExternalBenchmarkError("scenario result must contain a scenario_id")
        if scenario_id in rows:
            raise ExternalBenchmarkError(f"duplicate scenario result in campaign run: {scenario_id}")
        rows[scenario_id] = scenario
    return rows


def _agent_signature(value: object) -> tuple[str, str, str]:
    agent = _require_object(value, "agent")
    return (
        str(agent.get("provider", "")),
        str(agent.get("model", "")),
        str(agent.get("harness", "")),
    )


def _handoff_signature(value: object) -> tuple[object, ...] | None:
    if value is None:
        return None
    handoff = _require_object(value, "handoff")
    return (
        str(handoff.get("kind", "")),
        _agent_signature(handoff.get("source_agent", {})),
        _agent_signature(handoff.get("target_agent", {})),
        handoff.get("transcript_reused"),
    )


def _comparability_reasons(
    campaign: Mapping[str, Any],
    provider_runs: Mapping[str, list[Mapping[str, Any]]],
    repetitions: int,
) -> list[str]:
    reasons: list[str] = []
    provider_ids = [str(item["id"]) for item in campaign["configurations"]]
    scenario_ids = [str(item["scenario_id"]) for item in campaign["scenarios"]]
    reference_provider = provider_ids[0]
    canonical = provider_runs[reference_provider][0]
    canonical_execution = _require_object(canonical["execution"], "reference execution")
    canonical_timeout_policy = _require_object(
        canonical.get("_timeout_policy"), "reference timeout policy"
    )
    canonical_scenarios = _scenario_map(canonical)

    for provider_id in provider_ids:
        first = provider_runs[provider_id][0]
        provider_version = str(_require_object(first["provider"], "provider").get("version", ""))
        profile_identity = provider_profile_identity(
            _require_object(first["_provider_profile"], "provider profile")
        )
        for repetition in range(1, repetitions + 1):
            candidate = provider_runs[provider_id][repetition - 1]
            invalid_rows = [
                item
                for item in candidate.get("results", [])
                if isinstance(item, dict)
                and item.get("status") in {"INVALID_OPERATIONAL_RUN", "INVALID_EXECUTION_EVIDENCE"}
            ]
            if invalid_rows:
                reasons.append(
                    f"run-{repetition}: {provider_id} contains invalid operational/execution results"
                )
            candidate_execution = _require_object(candidate["execution"], "candidate execution")
            for key in _COMPARABILITY_KEYS:
                canonical_value = canonical_execution.get(key, _LEGACY_EXECUTION_PROTOCOL)
                candidate_value = candidate_execution.get(key, _LEGACY_EXECUTION_PROTOCOL)
                if candidate_value != canonical_value:
                    reasons.append(
                        f"run-{repetition}: {provider_id} execution.{key} differs "
                        f"from canonical {reference_provider}/run-1"
                    )
            if candidate.get("_timeout_policy") != canonical_timeout_policy:
                reasons.append(
                    f"run-{repetition}: {provider_id} timeout policy differs "
                    f"from canonical {reference_provider}/run-1"
                )
            current_provider = _require_object(candidate["provider"], "provider")
            if str(current_provider.get("version", "")) != provider_version:
                reasons.append(
                    f"run-{repetition}: {provider_id} provider version differs from its run-1"
                )
            candidate_profile = provider_profile_identity(
                _require_object(candidate["_provider_profile"], "provider profile")
            )
            if candidate_profile != profile_identity:
                reasons.append(
                    f"run-{repetition}: {provider_id} provider profile differs from its run-1"
                )

            candidate_scenarios = _scenario_map(candidate)
            if set(candidate_scenarios) != set(canonical_scenarios):
                reasons.append(
                    f"run-{repetition}: {provider_id} scenario set differs "
                    f"from canonical {reference_provider}/run-1"
                )
                continue
            for scenario_id in scenario_ids:
                left = canonical_scenarios.get(scenario_id)
                right = candidate_scenarios.get(scenario_id)
                if left is None or right is None:
                    reasons.append(f"run-{repetition}: missing scenario {scenario_id}")
                    continue
                if right.get("scenario_version") != left.get("scenario_version"):
                    reasons.append(
                        f"run-{repetition} {scenario_id}: scenario version differs for {provider_id}"
                    )
                if _agent_signature(right.get("agent", {})) != _agent_signature(left.get("agent", {})):
                    reasons.append(
                        f"run-{repetition} {scenario_id}: agent identity differs for {provider_id}"
                    )
                if _handoff_signature(right.get("handoff")) != _handoff_signature(left.get("handoff")):
                    reasons.append(
                        f"run-{repetition} {scenario_id}: handoff identity differs for {provider_id}"
                    )
    return sorted(set(reasons))


def _provider_summary(runs: list[Mapping[str, Any]]) -> dict[str, Any]:
    campaign_passed = sum(1 for run in runs if run["status"] == "PASS")
    scenario_total = 0
    scenario_passed = 0
    scenario_failed = 0
    scenario_invalid = 0
    agent_process_pass = 0
    agent_process_fail = 0
    nonzero_exits = 0
    timeouts = 0
    critical_failures = 0
    recalls: list[float] = []
    per_scenario: dict[str, dict[str, Any]] = {}
    for run in runs:
        for scenario in run["results"]:
            item = _require_object(scenario, "scenario result")
            scenario_id = str(item["scenario_id"])
            scenario_total += 1
            if item.get("status") in {"PASS", "VALID_PASS"}:
                scenario_passed += 1
            elif item.get("status") in {"FAIL", "VALID_FAIL"}:
                scenario_failed += 1
            elif item.get("status") in {"INVALID_OPERATIONAL_RUN", "INVALID_EXECUTION_EVIDENCE"}:
                scenario_invalid += 1
            dimensions = item.get("dimensions")
            process = dimensions.get("agent_process") if isinstance(dimensions, dict) else None
            if isinstance(process, dict):
                if process.get("status") == "PASS":
                    agent_process_pass += 1
                elif process.get("status") == "FAIL":
                    agent_process_fail += 1
                exits = process.get("nonzero_exits")
                timeout_rows = process.get("timeouts")
                if isinstance(exits, list):
                    nonzero_exits += len(exits)
                if isinstance(timeout_rows, list):
                    timeouts += len(timeout_rows)
            metrics = _require_object(item.get("metrics"), f"metrics for {scenario_id}")
            failures = metrics.get("critical_oracle_failures")
            if isinstance(failures, int):
                critical_failures += failures
            recall = metrics.get("invariant_recall_rate")
            if isinstance(recall, (int, float)):
                recalls.append(float(recall))
            summary = per_scenario.setdefault(
                scenario_id,
                {
                    "runs": 0,
                    "passed": 0,
                    "failed": 0,
                    "invalid": 0,
                    "critical_oracle_failures": 0,
                    "recalls": [],
                },
            )
            summary["runs"] += 1
            if item.get("status") in {"PASS", "VALID_PASS"}:
                summary["passed"] += 1
            elif item.get("status") in {"INVALID_OPERATIONAL_RUN", "INVALID_EXECUTION_EVIDENCE"}:
                summary["invalid"] += 1
            else:
                summary["failed"] += 1
            if isinstance(failures, int):
                summary["critical_oracle_failures"] += failures
            if isinstance(recall, (int, float)):
                summary["recalls"].append(float(recall))

    scenario_rows: dict[str, dict[str, Any]] = {}
    for scenario_id, summary in sorted(per_scenario.items()):
        values = list(summary.pop("recalls"))
        scenario_rows[scenario_id] = {
            **summary,
            "pass_rate": summary["passed"] / summary["runs"] if summary["runs"] else None,
            "mean_invariant_recall_rate": statistics.fmean(values) if values else None,
        }
    return {
        "provider_profile": dict(_require_object(runs[0]["_provider_profile"], "provider profile")),
        "campaign_runs_total": len(runs),
        "campaign_runs_passed": campaign_passed,
        "campaign_runs_failed": len(runs) - campaign_passed,
        "scenario_observations_total": scenario_total,
        "scenario_observations_passed": scenario_passed,
        "scenario_observations_failed": scenario_total - scenario_passed,
        "scenario_observations_valid_failed": scenario_failed,
        "scenario_observations_invalid": scenario_invalid,
        "scenario_pass_rate": scenario_passed / scenario_total if scenario_total else None,
        "critical_oracle_failures": critical_failures,
        "mean_invariant_recall_rate": statistics.fmean(recalls) if recalls else None,
        "agent_process_pass": agent_process_pass,
        "agent_process_fail": agent_process_fail,
        "nonzero_agent_exits": nonzero_exits,
        "timeouts": timeouts,
        "scenarios": scenario_rows,
    }


def compare_campaign(
    campaign: Mapping[str, Any],
    *,
    comparison_root: Path,
    repetitions: int | None = None,
) -> dict[str, Any]:
    comparison_root = comparison_root.resolve()
    if not comparison_root.is_dir():
        raise ExternalBenchmarkError("comparison root does not exist")
    if repetitions is None:
        repetitions = int(campaign["protocol"]["recommended_repetitions"])
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 1:
        raise ExternalBenchmarkError("comparison repetitions must be a positive integer")

    provider_ids = [str(item["id"]) for item in campaign["configurations"]]
    provider_runs: dict[str, list[Mapping[str, Any]]] = {}
    for provider_id in provider_ids:
        runs: list[Mapping[str, Any]] = []
        for repetition in range(1, repetitions + 1):
            run_dir = comparison_root / provider_id / f"run-{repetition}"
            result_path = run_dir / "campaign.json"
            plan_path = run_dir / "plan.json"
            result = _load_campaign_result(result_path)
            plan = _load_run_plan(
                plan_path,
                campaign=campaign,
                provider_id=provider_id,
                repetition=repetition,
            )
            if result.get("campaign_id") != campaign["campaign_id"]:
                raise ExternalBenchmarkError(f"campaign id mismatch: {result_path}")
            if result.get("campaign_version") != campaign["version"]:
                raise ExternalBenchmarkError(f"campaign version mismatch: {result_path}")
            provider = _require_object(result["provider"], "campaign result provider")
            if provider.get("id") != provider_id:
                raise ExternalBenchmarkError(f"provider id mismatch: {result_path}")
            execution = _require_object(result["execution"], "campaign result execution")
            if execution.get("repetition") != repetition:
                raise ExternalBenchmarkError(f"repetition metadata mismatch: {result_path}")
            _validate_plan_result_pair(plan, result, path=run_dir)
            row = dict(result)
            row["_provider_profile"] = dict(plan["provider_profile"])
            row["_timeout_policy"] = dict(plan["timeout_policy"])
            runs.append(row)
        provider_runs[provider_id] = runs

    reasons = _comparability_reasons(campaign, provider_runs, repetitions)
    summaries = {
        provider_id: _provider_summary(list(provider_runs[provider_id]))
        for provider_id in provider_ids
    }
    reference_execution = _require_object(
        provider_runs[provider_ids[0]][0]["execution"],
        "reference execution",
    )
    canonical_timeout_policy = _require_object(
        provider_runs[provider_ids[0]][0]["_timeout_policy"],
        "reference timeout policy",
    )
    comparable = not reasons
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "campaign_id": str(campaign["campaign_id"]),
        "campaign_version": str(campaign["version"]),
        "category": str(campaign["category"]),
        "status": "PASS" if comparable else "FAIL",
        "comparability": {
            "status": "COMPARABLE" if comparable else "NOT_COMPARABLE",
            "reasons": reasons,
            "repetitions": repetitions,
            "reference": {
                **{key: reference_execution.get(key) for key in _COMPARABILITY_KEYS},
                "timeout_policy": canonical_timeout_policy,
            },
        },
        "providers": summaries,
    }
