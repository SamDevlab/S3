"""Execution evidence and status semantics for real external benchmark runs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from .timeout_policy import ProcessResult

EXECUTION_PROTOCOL_VERSION = "agent-memory-v1.0.3"
PROCESS_METADATA_SCHEMA_VERSION = "1.0.0"
RESULT_SCHEMA_VERSION = "1.1.0"
VALID_RESULT_STATUSES = {
    "VALID_PASS",
    "VALID_FAIL",
    "INVALID_OPERATIONAL_RUN",
    "INVALID_EXECUTION_EVIDENCE",
}
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._+-]+$")


class ExecutionEvidenceError(ValueError):
    """Raised when structured agent-process evidence is malformed."""


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExecutionEvidenceError(f"{name} must be a JSON object")
    return value


def _agent(value: object, name: str) -> dict[str, str]:
    raw = _object(value, name)
    result: dict[str, str] = {}
    for key in ("provider", "model", "harness"):
        item = raw.get(key)
        if not isinstance(item, str) or not item:
            raise ExecutionEvidenceError(f"{name}.{key} must be a non-empty string")
        result[key] = item
    return result


def _safe_name(value: str, name: str) -> str:
    if not isinstance(value, str) or not _SAFE_NAME.fullmatch(value):
        raise ExecutionEvidenceError(f"{name} must be a safe non-empty identifier")
    return value


def process_metadata_path(directory: Path, scenario_id: str, phase: str) -> Path:
    """Return the deterministic path for one scenario phase's process evidence."""

    return directory / (
        f"{_safe_name(scenario_id, 'scenario_id')}."
        f"{_safe_name(phase, 'phase')}.json"
    )


def _safe_argv(argv: Sequence[str]) -> list[str]:
    """Keep argv useful for audit without persisting local absolute paths."""

    result: list[str] = []
    for index, item in enumerate(argv):
        if not isinstance(item, str) or not item:
            raise ExecutionEvidenceError("process argv must be a non-empty string list")
        if index == 0:
            result.append(Path(item).name or item)
        else:
            result.append(item)
    return result


def write_process_metadata(
    path: Path,
    *,
    scenario_id: str,
    phase: str,
    agent: Mapping[str, Any],
    runner: str,
    argv: Sequence[str],
    result: "ProcessResult",
    prompt_delivery: str | None = None,
    prompt_present: bool | None = None,
) -> dict[str, Any]:
    """Persist only structured process outcome metadata, never process output."""

    if not isinstance(runner, str) or not runner:
        raise ExecutionEvidenceError("process runner must be a non-empty string")
    document: dict[str, Any] = {
        "schema_version": PROCESS_METADATA_SCHEMA_VERSION,
        "execution_protocol_version": EXECUTION_PROTOCOL_VERSION,
        "scenario_id": _safe_name(scenario_id, "scenario_id"),
        "phase": _safe_name(phase, "phase"),
        "agent": _agent(dict(agent), "agent"),
        "runner": runner,
        "argv": _safe_argv(argv),
        "returncode": int(result.returncode),
        "timed_out": bool(result.timed_out),
        "elapsed_seconds": float(result.elapsed_seconds),
    }
    if prompt_delivery is not None or prompt_present is not None:
        if prompt_delivery != "stdin" or prompt_present is not True:
            raise ExecutionEvidenceError("prompt delivery evidence is invalid")
        document["prompt_delivery"] = prompt_delivery
        document["prompt_present"] = prompt_present
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return document


def _phase_metadata(raw: object, *, expected_scenario: str, expected_phase: str) -> dict[str, Any]:
    document = _object(raw, "process metadata")
    if document.get("schema_version") != PROCESS_METADATA_SCHEMA_VERSION:
        raise ExecutionEvidenceError("unsupported process metadata schema")
    if document.get("execution_protocol_version") != EXECUTION_PROTOCOL_VERSION:
        raise ExecutionEvidenceError("process metadata execution protocol version is invalid")
    if document.get("scenario_id") != expected_scenario:
        raise ExecutionEvidenceError("process metadata scenario id mismatch")
    if document.get("phase") != expected_phase:
        raise ExecutionEvidenceError("process metadata phase mismatch")
    agent = _agent(document.get("agent"), "process metadata agent")
    runner = document.get("runner")
    if not isinstance(runner, str) or not runner:
        raise ExecutionEvidenceError("process metadata runner is invalid")
    returncode = document.get("returncode")
    if not isinstance(returncode, int) or isinstance(returncode, bool):
        raise ExecutionEvidenceError("process metadata returncode is invalid")
    timed_out = document.get("timed_out")
    if not isinstance(timed_out, bool):
        raise ExecutionEvidenceError("process metadata timed_out is invalid")
    elapsed = document.get("elapsed_seconds")
    if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or elapsed < 0:
        raise ExecutionEvidenceError("process metadata elapsed_seconds is invalid")
    argv = document.get("argv")
    if not isinstance(argv, list) or any(not isinstance(item, str) or not item for item in argv):
        raise ExecutionEvidenceError("process metadata argv is invalid")
    result = {
        "phase": expected_phase,
        "agent": agent,
        "runner": runner,
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_seconds": float(elapsed),
    }
    if runner == "ai-memory-managed":
        if document.get("prompt_delivery") != "stdin":
            raise ExecutionEvidenceError(
                "managed process prompt delivery evidence is missing or invalid"
            )
        if document.get("prompt_present") is not True:
            raise ExecutionEvidenceError(
                "managed process prompt presence evidence is missing or invalid"
            )
        result["prompt_delivery"] = "stdin"
        result["prompt_present"] = True
    return result


def load_process_metadata(
    runbook: Mapping[str, Any],
    *,
    scenario_id: str,
    directory: Path,
) -> list[dict[str, Any]]:
    """Load every required process record for a scenario from its runbook."""

    rows = runbook.get("scenarios")
    if not isinstance(rows, list):
        raise ExecutionEvidenceError("runbook scenarios are invalid")
    matches = [row for row in rows if isinstance(row, dict) and row.get("scenario_id") == scenario_id]
    if len(matches) != 1:
        raise ExecutionEvidenceError("runbook scenario is not uniquely available")
    steps = matches[0].get("steps")
    if not isinstance(steps, list) or not steps:
        raise ExecutionEvidenceError("runbook scenario steps are invalid")
    directory = directory.resolve()
    result: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            raise ExecutionEvidenceError("runbook step is invalid")
        phase = step.get("id")
        if not isinstance(phase, str) or not phase:
            raise ExecutionEvidenceError("runbook step id is invalid")
        path = process_metadata_path(directory, scenario_id, phase)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise ExecutionEvidenceError(f"missing process metadata: {path.name}") from error
        except json.JSONDecodeError as error:
            raise ExecutionEvidenceError(f"invalid process metadata JSON: {path.name}") from error
        result.append(_phase_metadata(raw, expected_scenario=scenario_id, expected_phase=phase))
    return result


def classify_process_phases(phases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Classify required agent phases; nonzero completion is a valid failure."""

    clean: list[dict[str, Any]] = []
    nonzero: list[dict[str, Any]] = []
    timeouts: list[dict[str, Any]] = []
    for raw in phases:
        if raw.get("schema_version") is not None:
            phase = _phase_metadata(
                raw,
                expected_scenario=str(raw.get("scenario_id", "")),
                expected_phase=str(raw.get("phase", "")),
            )
        else:
            phase = dict(raw)
            if phase.get("runner") == "ai-memory-managed":
                if phase.get("prompt_delivery") != "stdin" or phase.get("prompt_present") is not True:
                    raise ExecutionEvidenceError(
                        "managed process prompt delivery evidence is missing or invalid"
                    )
        clean.append(phase)
        if phase["timed_out"]:
            timeouts.append({"phase": phase["phase"], "elapsed_seconds": phase["elapsed_seconds"]})
        elif phase["returncode"] != 0:
            nonzero.append(
                {"phase": phase["phase"], "returncode": phase["returncode"]}
            )
    if timeouts:
        status = "INVALID_OPERATIONAL_RUN"
    elif nonzero:
        status = "FAIL"
    else:
        status = "PASS"
    return {
        "status": status,
        "phases": clean,
        "required_processes": len(clean),
        "nonzero_exits": nonzero,
        "timeouts": timeouts,
    }


def invalid_process_evidence(reason: str) -> dict[str, Any]:
    return {
        "status": "INVALID_EXECUTION_EVIDENCE",
        "phases": [],
        "required_processes": 0,
        "nonzero_exits": [],
        "timeouts": [],
        "reason": reason,
    }


def is_new_execution_protocol(execution: Mapping[str, Any]) -> bool:
    return execution.get("execution_protocol_version") == EXECUTION_PROTOCOL_VERSION
