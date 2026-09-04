"""Cross-provider comparison for versioned external benchmark campaigns."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Mapping

from .campaign import CAMPAIGN_RESULT_SCHEMA_VERSION
from .core import ExternalBenchmarkError

COMPARISON_SCHEMA_VERSION = "1.0.0"
_COMPARABILITY_KEYS = (
    "s3_commit",
    "agent_harness_version",
    "tool_permissions_profile",
    "task_protocol_version",
)


def _require_object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalBenchmarkError(f"{name} must be a JSON object")
    return value


def _load_campaign_result(path: Path) -> dict[str, Any]:
    try:
        document = _require_object(
            json.loads(path.read_text(encoding="utf-8")),
            "campaign result",
        )
    except OSError as error:
        raise ExternalBenchmarkError(f"missing campaign result: {path}") from error
    except json.JSONDecodeError as error:
        raise ExternalBenchmarkError(f"invalid campaign result JSON: {path}") from error
    if document.get("schema_version") != CAMPAIGN_RESULT_SCHEMA_VERSION:
        raise ExternalBenchmarkError(f"unsupported campaign result schema: {path}")
    if document.get("status") not in {"PASS", "FAIL"}:
        raise ExternalBenchmarkError(f"invalid campaign result status: {path}")
    _require_object(document.get("provider"), "campaign result provider")
    _require_object(document.get("execution"), "campaign result execution")
    if not isinstance(document.get("results"), list):
        raise ExternalBenchmarkError(f"campaign result results must be a list: {path}")
    return document


def _scenario_map(result: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}
    for item in result["results"]:
        scenario = _require_object(item, "scenario result")
        scenario_id = scenario.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise ExternalBenchmarkError("scenario result must contain a scenario_id")
        if scenario_id in rows:
            raise ExternalBenchmarkError(
                f"duplicate scenario result in campaign run: {scenario_id}"
            )
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
    canonical_scenarios = _scenario_map(canonical)

    for provider_id in provider_ids:
        provider_version = str(
            _require_object(provider_runs[provider_id][0]["provider"], "provider").get(
                "version", ""
            )
        )
        for repetition in range(1, repetitions + 1):
            candidate = provider_runs[provider_id][repetition - 1]
            candidate_execution = _require_object(
                candidate["execution"],
                "candidate execution",
            )
            for key in _COMPARABILITY_KEYS:
                if candidate_execution.get(key) != canonical_execution.get(key):
                    reasons.append(
                        f"run-{repetition}: {provider_id} execution.{key} differs "
                        f"from canonical {reference_provider}/run-1"
                    )

            current_provider = _require_object(candidate["provider"], "provider")
            if str(current_provider.get("version", "")) != provider_version:
                reasons.append(
                    f"run-{repetition}: {provider_id} provider version differs "
                    "from its run-1"
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
                        f"run-{repetition} {scenario_id}: scenario version differs "
                        f"for {provider_id}"
                    )
                if _agent_signature(right.get("agent", {})) != _agent_signature(
                    left.get("agent", {})
                ):
                    reasons.append(
                        f"run-{repetition} {scenario_id}: agent identity differs "
                        f"for {provider_id}"
                    )
                if _handoff_signature(right.get("handoff")) != _handoff_signature(
                    left.get("handoff")
                ):
                    reasons.append(
                        f"run-{repetition} {scenario_id}: handoff identity differs "
                        f"for {provider_id}"
                    )
    return sorted(set(reasons))


def _provider_summary(runs: list[Mapping[str, Any]]) -> dict[str, Any]:
    campaign_passed = sum(1 for run in runs if run["status"] == "PASS")
    scenario_total = 0
    scenario_passed = 0
    critical_failures = 0
    recalls: list[float] = []
    per_scenario: dict[str, dict[str, Any]] = {}

    for run in runs:
        for scenario in run["results"]:
            item = _require_object(scenario, "scenario result")
            scenario_id = str(item["scenario_id"])
            scenario_total += 1
            if item.get("status") == "PASS":
                scenario_passed += 1
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
                    "critical_oracle_failures": 0,
                    "recalls": [],
                },
            )
            summary["runs"] += 1
            if item.get("status") == "PASS":
                summary["passed"] += 1
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
            "pass_rate": (
                summary["passed"] / summary["runs"] if summary["runs"] else None
            ),
            "mean_invariant_recall_rate": (
                statistics.fmean(values) if values else None
            ),
        }

    return {
        "campaign_runs_total": len(runs),
        "campaign_runs_passed": campaign_passed,
        "campaign_runs_failed": len(runs) - campaign_passed,
        "scenario_observations_total": scenario_total,
        "scenario_observations_passed": scenario_passed,
        "scenario_observations_failed": scenario_total - scenario_passed,
        "scenario_pass_rate": (
            scenario_passed / scenario_total if scenario_total else None
        ),
        "critical_oracle_failures": critical_failures,
        "mean_invariant_recall_rate": statistics.fmean(recalls) if recalls else None,
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
            path = comparison_root / provider_id / f"run-{repetition}" / "campaign.json"
            result = _load_campaign_result(path)
            if result.get("campaign_id") != campaign["campaign_id"]:
                raise ExternalBenchmarkError(f"campaign id mismatch: {path}")
            if result.get("campaign_version") != campaign["version"]:
                raise ExternalBenchmarkError(f"campaign version mismatch: {path}")
            provider = _require_object(result["provider"], "campaign result provider")
            if provider.get("id") != provider_id:
                raise ExternalBenchmarkError(f"provider id mismatch: {path}")
            execution = _require_object(result["execution"], "campaign result execution")
            if execution.get("repetition") != repetition:
                raise ExternalBenchmarkError(f"repetition metadata mismatch: {path}")
            runs.append(result)
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
                key: reference_execution.get(key)
                for key in _COMPARABILITY_KEYS
            },
        },
        "providers": summaries,
    }
