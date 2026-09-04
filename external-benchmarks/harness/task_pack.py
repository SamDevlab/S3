"""Versioned Agent Memory task packs and change-artifact validation."""

from __future__ import annotations

import fnmatch
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

TASK_PACK_SCHEMA_VERSION = "1.0.0"
_AGENT_REPORT_NAME = ".s3-agent-memory-report.json"


class TaskPackError(RuntimeError):
    """A task pack, rendered task, or expected artifact contract is invalid."""


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TaskPackError(f"{name} must be a JSON object")
    return value


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TaskPackError(f"{name} must be a non-empty string")
    return value


def _safe_pattern(value: object, name: str) -> str:
    pattern = _string(value, name)
    path = Path(pattern)
    if path.is_absolute() or ".." in path.parts:
        raise TaskPackError(f"{name} must be repository-relative")
    return pattern.replace("\\", "/")


def load_task_pack(path: Path) -> dict[str, Any]:
    try:
        document = _object(json.loads(path.read_text(encoding="utf-8")), "task pack")
    except OSError as error:
        raise TaskPackError("task pack could not be read") from error
    except json.JSONDecodeError as error:
        raise TaskPackError("task pack is not valid JSON") from error
    if document.get("schema_version") != TASK_PACK_SCHEMA_VERSION:
        raise TaskPackError("unsupported task-pack schema")
    _string(document.get("campaign_id"), "task pack campaign_id")
    _string(document.get("version"), "task pack version")
    rules = document.get("global_rules")
    rows = document.get("scenarios")
    if not isinstance(rules, list) or any(not isinstance(item, str) or not item for item in rules):
        raise TaskPackError("task pack global_rules must be a string list")
    if not isinstance(rows, list) or not rows:
        raise TaskPackError("task pack scenarios must be a non-empty list")
    ids: list[str] = []
    for raw in rows:
        row = _object(raw, "task-pack scenario")
        scenario_id = _string(row.get("scenario_id"), "task-pack scenario_id")
        ids.append(scenario_id)
        for phase_name in ("phase_a", "phase_b"):
            phase = _object(row.get(phase_name), phase_name)
            _string(phase.get("instruction"), f"{phase_name}.instruction")
            paths = phase.get("authoritative_paths")
            if not isinstance(paths, list):
                raise TaskPackError(f"{phase_name}.authoritative_paths must be a list")
            for item in paths:
                _safe_pattern(item, f"{phase_name}.authoritative_path")
            expose = phase.get("expose_invariants")
            if expose is not None and not isinstance(expose, bool):
                raise TaskPackError(f"{phase_name}.expose_invariants must be boolean")
        artifacts = _object(row.get("expected_artifacts"), "expected_artifacts")
        for key in ("required_changed", "forbidden_changed"):
            values = artifacts.get(key)
            if not isinstance(values, list):
                raise TaskPackError(f"expected_artifacts.{key} must be a list")
            for item in values:
                _safe_pattern(item, f"expected_artifacts.{key}")
        alternatives = artifacts.get("required_changed_any", [])
        if not isinstance(alternatives, list):
            raise TaskPackError("expected_artifacts.required_changed_any must be a list")
        for group in alternatives:
            if not isinstance(group, list) or not group:
                raise TaskPackError(
                    "expected_artifacts.required_changed_any entries must be non-empty lists"
                )
            for item in group:
                _safe_pattern(item, "required_changed_any")
        maximum = artifacts.get("max_changed_files")
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
            raise TaskPackError("expected_artifacts.max_changed_files must be positive")
    if len(ids) != len(set(ids)):
        raise TaskPackError("task-pack scenario ids must be unique")
    return document


def task_for_scenario(task_pack: Mapping[str, Any], scenario_id: str) -> dict[str, Any]:
    rows = task_pack.get("scenarios")
    if not isinstance(rows, list):
        raise TaskPackError("task pack scenarios are invalid")
    matches = [row for row in rows if isinstance(row, dict) and row.get("scenario_id") == scenario_id]
    if len(matches) != 1:
        raise TaskPackError(f"scenario is not uniquely present in task pack: {scenario_id}")
    return matches[0]


def _memory_policy(provider_profile: Mapping[str, Any], phase: str) -> str:
    mode = provider_profile.get("memory_mode")
    gate = provider_profile.get("integrity_gate")
    if mode == "none":
        return (
            "This arm has no durable memory. Do not create hidden notes or handoff files. "
            "At a hard boundary, all native session context is discarded."
        )
    if mode == "context-only":
        return (
            "This arm may use the active native context only. Do not use an external durable "
            "memory service or hidden handoff file; a hard boundary starts a fresh context."
        )
    if mode == "ai-memory":
        enabled = isinstance(gate, dict) and gate.get("enabled") is True
        suffix = (
            "Durable memory proposals are subject to the S3 integrity gate."
            if enabled
            else "No S3 integrity gate is active for this arm."
        )
        return (
            "AI-MEMORY is the only permitted durable handoff channel. Do not use native "
            f"transcript resume across hard boundaries. {suffix}"
        )
    raise TaskPackError("unsupported provider memory mode")


def render_phase_prompt(
    task_pack: Mapping[str, Any],
    scenario: Mapping[str, Any],
    provider_profile: Mapping[str, Any],
    *,
    phase: str,
) -> str:
    """Render one phase without leaking future-phase oracle expectations."""

    if phase not in {"a", "b"}:
        raise TaskPackError("phase must be 'a' or 'b'")
    scenario_id = _string(scenario.get("scenario_id"), "scenario_id")
    task = task_for_scenario(task_pack, scenario_id)
    phase_data = _object(task.get(f"phase_{phase}"), f"phase_{phase}")
    lines = [
        f"# Agent Memory V1 — {scenario_id} — Phase {phase.upper()}",
        "",
        _memory_policy(provider_profile, phase),
        "",
        _string(phase_data.get("instruction"), "phase instruction"),
        "",
    ]
    if phase == "a":
        paths = phase_data.get("authoritative_paths", [])
        if paths:
            lines.extend(["Authoritative paths to inspect:", *[f"- `{path}`" for path in paths], ""])
        if phase_data.get("expose_invariants", True):
            invariants = scenario.get("critical_invariants")
            if not isinstance(invariants, list):
                raise TaskPackError("scenario critical_invariants must be a list")
            lines.append("Contracts to preserve across the boundary:")
            for raw in invariants:
                invariant = _object(raw, "critical invariant")
                lines.append(
                    f"- `{_string(invariant.get('id'), 'invariant id')}`: "
                    f"{_string(invariant.get('description'), 'invariant description')}"
                )
            lines.append("")
    else:
        lines.extend(
            [
                "Do not request or reuse the Phase A transcript. Use only the current S3 checkout",
                "plus the memory channel permitted by this experimental arm.",
                "",
                "The current checkout is authoritative if any remembered claim conflicts with it.",
                "",
            ]
        )
    rules = task_pack.get("global_rules", [])
    if rules:
        lines.append("Protocol rules:")
        lines.extend(f"- {rule}" for rule in rules)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _git_names(repository_root: Path, base_commit: str) -> list[str]:
    commands = (
        ("git", "-C", str(repository_root), "diff", "--name-only", base_commit, "--"),
        ("git", "-C", str(repository_root), "ls-files", "--others", "--exclude-standard"),
    )
    names: set[str] = set()
    for argv in commands:
        try:
            completed = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                shell=False,
                check=False,
            )
        except OSError as error:
            raise TaskPackError("git is unavailable for artifact validation") from error
        if completed.returncode != 0:
            raise TaskPackError(f"git artifact inspection failed: {completed.stderr.strip()}")
        names.update(line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip())
    names.discard(_AGENT_REPORT_NAME)
    return sorted(names)


def validate_task_artifacts(
    task: Mapping[str, Any],
    *,
    repository_root: Path,
    base_commit: str,
) -> list[dict[str, object]]:
    """Validate that a coding task produced the required scoped repository changes."""

    repository_root = repository_root.resolve()
    if not repository_root.is_dir():
        raise TaskPackError("task repository root does not exist")
    if not isinstance(base_commit, str) or not base_commit:
        raise TaskPackError("task base commit is invalid")
    artifacts = _object(task.get("expected_artifacts"), "expected_artifacts")
    changed = _git_names(repository_root, base_commit)
    rows: list[dict[str, object]] = []
    rows.append(
        {
            "id": "task-nonempty-change",
            "kind": "task_artifact",
            "passed": bool(changed),
            "detail": f"changed_files={len(changed)}",
        }
    )
    for raw_pattern in artifacts.get("required_changed", []):
        pattern = _safe_pattern(raw_pattern, "required_changed")
        matches = [path for path in changed if fnmatch.fnmatch(path, pattern)]
        rows.append(
            {
                "id": f"task-required:{pattern}",
                "kind": "task_artifact",
                "passed": bool(matches),
                "detail": "matches=" + (",".join(matches) if matches else "none"),
            }
        )
    for raw_group in artifacts.get("required_changed_any", []):
        if not isinstance(raw_group, list) or not raw_group:
            raise TaskPackError("required_changed_any entries must be non-empty lists")
        patterns = [_safe_pattern(item, "required_changed_any") for item in raw_group]
        matches = [
            path for path in changed if any(fnmatch.fnmatch(path, pattern) for pattern in patterns)
        ]
        rows.append(
            {
                "id": "task-required-any:" + "|".join(patterns),
                "kind": "task_artifact",
                "passed": bool(matches),
                "detail": "matches=" + (",".join(matches) if matches else "none"),
            }
        )
    for raw_pattern in artifacts.get("forbidden_changed", []):
        pattern = _safe_pattern(raw_pattern, "forbidden_changed")
        matches = [path for path in changed if fnmatch.fnmatch(path, pattern)]
        rows.append(
            {
                "id": f"task-forbidden:{pattern}",
                "kind": "task_artifact",
                "passed": not matches,
                "detail": "matches=" + (",".join(matches) if matches else "none"),
            }
        )
    maximum = artifacts.get("max_changed_files")
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
        raise TaskPackError("max_changed_files is invalid")
    rows.append(
        {
            "id": "task-change-budget",
            "kind": "task_artifact",
            "passed": len(changed) <= maximum,
            "detail": f"changed_files={len(changed)},max={maximum}",
        }
    )
    return rows


def attach_task_checks(result: dict[str, Any], checks: list[dict[str, object]]) -> dict[str, Any]:
    """Attach task-artifact gates to a scenario result using the existing correctness semantics."""

    oracle = result.get("oracle")
    metrics = result.get("metrics")
    if not isinstance(oracle, list) or not isinstance(metrics, dict):
        raise TaskPackError("scenario result cannot accept task checks")
    oracle.extend(checks)
    failed = sum(1 for row in checks if row.get("passed") is not True)
    metrics["oracle_checks_total"] = int(metrics.get("oracle_checks_total", 0)) + len(checks)
    metrics["oracle_checks_passed"] = int(metrics.get("oracle_checks_passed", 0)) + len(checks) - failed
    metrics["critical_oracle_failures"] = int(metrics.get("critical_oracle_failures", 0)) + failed
    if failed:
        result["status"] = "FAIL"
    return result
