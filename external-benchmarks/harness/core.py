"""Correctness oracle for repository-local external benchmarks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "1.0.0"


class ExternalBenchmarkError(RuntimeError):
    """An external benchmark input or oracle execution is invalid."""


def _require_object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalBenchmarkError(f"{name} must be a JSON object")
    return value


def load_scenario(path: Path) -> dict[str, Any]:
    document = _require_object(json.loads(path.read_text(encoding="utf-8")), "scenario")
    required = {"schema_version", "scenario_id", "version", "category", "objective", "critical_invariants", "oracle"}
    missing = sorted(required.difference(document))
    if missing:
        raise ExternalBenchmarkError(f"scenario missing required fields: {', '.join(missing)}")
    if document["schema_version"] != SCHEMA_VERSION:
        raise ExternalBenchmarkError("unsupported external benchmark scenario schema")
    if not isinstance(document["critical_invariants"], list):
        raise ExternalBenchmarkError("critical_invariants must be a list")
    _require_object(document["oracle"], "oracle")
    return document


def list_scenarios(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(root.glob("*.json")):
        scenario = load_scenario(path)
        rows.append(
            {
                "scenario_id": str(scenario["scenario_id"]),
                "version": str(scenario["version"]),
                "category": str(scenario["category"]),
                "objective": str(scenario["objective"]),
            }
        )
    return rows


def _expand_argument(value: str) -> str:
    return sys.executable if value == "{python}" else value


def _command_check(check: Mapping[str, Any], repository_root: Path) -> dict[str, Any]:
    argv = check.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise ExternalBenchmarkError("oracle command argv must be a non-empty string list")
    timeout = check.get("timeout_seconds", 120)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ExternalBenchmarkError("oracle command timeout_seconds must be positive")
    arguments = [_expand_argument(item) for item in argv]
    try:
        completed = subprocess.run(
            arguments,
            cwd=repository_root,
            capture_output=True,
            text=True,
            shell=False,
            timeout=float(timeout),
            check=False,
        )
        passed = completed.returncode == 0
        detail = f"exit_code={completed.returncode}"
    except subprocess.TimeoutExpired:
        passed = False
        detail = "timed_out=true"
    return {
        "id": str(check.get("id", "command")),
        "kind": "command",
        "passed": passed,
        "detail": detail,
    }


def _matching_files(repository_root: Path, pattern: str) -> list[Path]:
    if not pattern or Path(pattern).is_absolute() or ".." in Path(pattern).parts:
        raise ExternalBenchmarkError("oracle glob must be a non-empty repository-relative pattern")
    return sorted(path for path in repository_root.glob(pattern) if path.is_file())


def _pattern_check(check: Mapping[str, Any], repository_root: Path, *, forbidden: bool) -> dict[str, Any]:
    glob = check.get("glob")
    pattern = check.get("pattern")
    if not isinstance(glob, str) or not isinstance(pattern, str) or not pattern:
        raise ExternalBenchmarkError("pattern oracle requires glob and non-empty pattern strings")
    files = _matching_files(repository_root, glob)
    matches: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if pattern in text:
            matches.append(path.relative_to(repository_root).as_posix())
    passed = not matches if forbidden else bool(matches)
    detail = "matches=" + (",".join(matches) if matches else "none")
    return {
        "id": str(check.get("id", "pattern")),
        "kind": "forbidden_pattern" if forbidden else "required_pattern",
        "passed": passed,
        "detail": detail,
    }


def _safe_provider(observation: Mapping[str, Any]) -> dict[str, str]:
    provider = _require_object(observation.get("provider"), "provider")
    provider_id = provider.get("id")
    if not isinstance(provider_id, str) or not provider_id:
        raise ExternalBenchmarkError("provider.id must be a non-empty string")
    version = provider.get("version")
    if version is not None and not isinstance(version, str):
        raise ExternalBenchmarkError("provider.version must be a string when present")
    return {"id": provider_id, "version": version or "unknown"}


def _safe_agent_value(value: object, name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ExternalBenchmarkError(f"{name} must be a JSON object")
    allowed = ("provider", "model", "harness")
    result: dict[str, str] = {}
    for key in allowed:
        item = value.get(key)
        if item is not None:
            if not isinstance(item, str):
                raise ExternalBenchmarkError(f"{name}.{key} must be a string")
            result[key] = item
    return result


def _safe_agent(observation: Mapping[str, Any]) -> dict[str, str]:
    return _safe_agent_value(observation.get("agent", {}), "agent")


def _safe_handoff(observation: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = observation.get("handoff")
    if raw is None:
        return None
    handoff = _require_object(raw, "handoff")
    kind = handoff.get("kind")
    if kind not in {"cross-session", "cross-agent"}:
        raise ExternalBenchmarkError("handoff.kind must be cross-session or cross-agent")
    transcript_reused = handoff.get("transcript_reused")
    if not isinstance(transcript_reused, bool):
        raise ExternalBenchmarkError("handoff.transcript_reused must be boolean")
    return {
        "kind": kind,
        "source_agent": _safe_agent_value(handoff.get("source_agent", {}), "handoff.source_agent"),
        "target_agent": _safe_agent_value(handoff.get("target_agent", {}), "handoff.target_agent"),
        "transcript_reused": transcript_reused,
    }


def _safe_stale_memory(observation: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = observation.get("stale_memory")
    if raw is None:
        return None
    stale = _require_object(raw, "stale_memory")
    claim_id = stale.get("claim_id")
    injected = stale.get("injected")
    if not isinstance(claim_id, str) or not claim_id:
        raise ExternalBenchmarkError("stale_memory.claim_id must be a non-empty string")
    if not isinstance(injected, bool):
        raise ExternalBenchmarkError("stale_memory.injected must be boolean")
    return {"claim_id": claim_id, "injected": injected}


def evaluate_scenario(
    scenario: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    if not repository_root.is_dir():
        raise ExternalBenchmarkError("repository root does not exist")

    critical = scenario.get("critical_invariants", [])
    invariant_ids: list[str] = []
    for item in critical:
        invariant = _require_object(item, "critical invariant")
        invariant_id = invariant.get("id")
        if not isinstance(invariant_id, str) or not invariant_id:
            raise ExternalBenchmarkError("critical invariant id must be a non-empty string")
        invariant_ids.append(invariant_id)

    reported = observation.get("reported_invariants", [])
    if not isinstance(reported, list) or any(not isinstance(item, str) for item in reported):
        raise ExternalBenchmarkError("reported_invariants must be a string list")
    recalled = sorted(set(invariant_ids).intersection(reported))

    oracle = _require_object(scenario.get("oracle"), "oracle")
    results: list[dict[str, Any]] = []
    for check in oracle.get("commands", []):
        results.append(_command_check(_require_object(check, "command check"), repository_root))
    for check in oracle.get("required_patterns", []):
        results.append(_pattern_check(_require_object(check, "required pattern check"), repository_root, forbidden=False))
    for check in oracle.get("forbidden_patterns", []):
        results.append(_pattern_check(_require_object(check, "forbidden pattern check"), repository_root, forbidden=True))

    failed = [item for item in results if not item["passed"]]
    total = len(invariant_ids)
    metrics = {
        "critical_invariants_total": total,
        "critical_invariants_reported": len(recalled),
        "invariant_recall_rate": (len(recalled) / total) if total else None,
        "oracle_checks_total": len(results),
        "oracle_checks_passed": len(results) - len(failed),
        "critical_oracle_failures": len(failed),
    }
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": str(scenario["scenario_id"]),
        "scenario_version": str(scenario["version"]),
        "category": str(scenario["category"]),
        "provider": _safe_provider(observation),
        "agent": _safe_agent(observation),
        "status": "FAIL" if failed else "PASS",
        "reported_invariants": recalled,
        "metrics": metrics,
        "oracle": results,
    }
    handoff = _safe_handoff(observation)
    if handoff is not None:
        result["handoff"] = handoff
    stale_memory = _safe_stale_memory(observation)
    if stale_memory is not None:
        result["stale_memory"] = stale_memory
    return result
