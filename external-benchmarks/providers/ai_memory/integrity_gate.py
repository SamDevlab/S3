"""Deterministic S3 integrity scorer for AI-MEMORY auto-improve proposals."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, TextIO

GATE_SCHEMA_VERSION = "1.0.0"
REGISTRY_SCHEMA_VERSION = "1.0.0"
MAX_INPUT_CHARS = 1_000_000
MAX_BODY_CHARS = 250_000


class IntegrityGateError(RuntimeError):
    """The local scorer contract or invariant registry is invalid."""


def repository_root_from_module() -> Path:
    return Path(__file__).resolve().parents[3]


def default_registry_path(repository_root: Path) -> Path:
    return repository_root / "external-benchmarks" / "invariants" / "agent-memory-v1.json"


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IntegrityGateError(f"{name} must be an object")
    return value


def _string(value: object, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise IntegrityGateError(f"{name} must be a string")
    return value


def load_registry(path: Path) -> dict[str, Any]:
    try:
        document = _object(json.loads(path.read_text(encoding="utf-8")), "registry")
    except OSError as error:
        raise IntegrityGateError("integrity registry is unavailable") from error
    except json.JSONDecodeError as error:
        raise IntegrityGateError("integrity registry is invalid JSON") from error
    if document.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise IntegrityGateError("unsupported integrity registry schema")
    invariants = document.get("invariants")
    if not isinstance(invariants, list) or not invariants:
        raise IntegrityGateError("integrity registry must contain invariants")

    ids: list[str] = []
    for raw in invariants:
        invariant = _object(raw, "invariant")
        invariant_id = _string(invariant.get("id"), "invariant.id")
        ids.append(invariant_id)
        evidence = invariant.get("evidence")
        patterns = invariant.get("contradiction_patterns")
        if not isinstance(evidence, list) or not evidence:
            raise IntegrityGateError(f"invariant {invariant_id} must contain evidence")
        if not isinstance(patterns, list) or not patterns:
            raise IntegrityGateError(
                f"invariant {invariant_id} must contain contradiction patterns"
            )
        for pattern in patterns:
            pattern_text = _string(pattern, f"pattern for {invariant_id}")
            try:
                re.compile(pattern_text)
            except re.error as error:
                raise IntegrityGateError(
                    f"invariant {invariant_id} contains invalid regex"
                ) from error
    if len(ids) != len(set(ids)):
        raise IntegrityGateError("integrity invariant ids must be unique")
    return document


def validate_registry_evidence(
    registry: Mapping[str, Any],
    *,
    repository_root: Path,
) -> list[str]:
    """Return invariant ids whose claimed repository evidence no longer holds."""

    repository_root = repository_root.resolve()
    stale: list[str] = []
    for raw in registry["invariants"]:
        invariant = _object(raw, "invariant")
        invariant_id = str(invariant["id"])
        invariant_stale = False
        for raw_evidence in invariant["evidence"]:
            evidence = _object(raw_evidence, f"evidence for {invariant_id}")
            relative = Path(_string(evidence.get("path"), "evidence.path"))
            if relative.is_absolute() or ".." in relative.parts:
                raise IntegrityGateError("integrity evidence paths must be repository-relative")
            path = (repository_root / relative).resolve()
            try:
                path.relative_to(repository_root)
            except ValueError as error:
                raise IntegrityGateError("integrity evidence path escapes repository") from error
            required = evidence.get("required_literals")
            if not isinstance(required, list) or not required:
                raise IntegrityGateError(f"evidence for {invariant_id} needs required_literals")
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                invariant_stale = True
                continue
            for literal in required:
                literal_text = _string(literal, "evidence literal")
                if literal_text not in text:
                    invariant_stale = True
        if invariant_stale:
            stale.append(invariant_id)
    return sorted(stale)


def contradiction_ids(text: str, registry: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    for raw in registry["invariants"]:
        invariant = _object(raw, "invariant")
        invariant_id = str(invariant["id"])
        if any(re.search(str(pattern), text) for pattern in invariant["contradiction_patterns"]):
            violations.append(invariant_id)
    return sorted(violations)


def _score(violations: list[str], total: int) -> float:
    return round(1.0 - (len(set(violations)) / total), 6)


def evaluate_proposal(
    proposal: Mapping[str, Any],
    *,
    repository_root: Path,
    registry_path: Path | None = None,
) -> dict[str, object]:
    """Evaluate one AI-MEMORY auto-improve proposal against current S3 evidence."""

    for field in ("path", "kind", "operation", "title", "rationale"):
        _string(proposal.get(field), field, allow_empty=field in {"title", "rationale"})
    before_body = _string(proposal.get("before_body", ""), "before_body", allow_empty=True)
    after_body = _string(proposal.get("after_body"), "after_body", allow_empty=True)
    if len(before_body) > MAX_BODY_CHARS or len(after_body) > MAX_BODY_CHARS:
        raise IntegrityGateError("proposal body exceeds scorer limit")

    repository_root = repository_root.resolve()
    registry = load_registry(registry_path or default_registry_path(repository_root))
    stale_evidence = validate_registry_evidence(registry, repository_root=repository_root)
    if stale_evidence:
        return {
            "score_before": 0.0,
            "score_after": 0.0,
            "passed": False,
            "reason": "S3 integrity registry evidence mismatch: " + ", ".join(stale_evidence),
        }

    before_violations = contradiction_ids(before_body, registry)
    after_violations = contradiction_ids(after_body, registry)
    total = len(registry["invariants"])
    response: dict[str, object] = {
        "score_before": _score(before_violations, total),
        "score_after": _score(after_violations, total),
        "passed": not after_violations,
    }
    if after_violations:
        response["reason"] = "Contradicts S3 invariant: " + ", ".join(after_violations)
    else:
        response["reason"] = "No registered S3 invariant contradiction detected"
    return response


def _failure(reason: str) -> dict[str, object]:
    bounded = reason.replace("\n", " ").strip()[:240] or "S3 integrity gate rejected input"
    return {"passed": False, "reason": bounded}


def main(
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    repository_root: Path | None = None,
    registry_path: Path | None = None,
) -> int:
    """Read one proposal JSON object from stdin and print one scorer JSON object."""

    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    try:
        raw = input_stream.read(MAX_INPUT_CHARS + 1)
        if len(raw) > MAX_INPUT_CHARS:
            response = _failure("proposal input exceeds scorer limit")
        else:
            proposal = _object(json.loads(raw), "proposal")
            response = evaluate_proposal(
                proposal,
                repository_root=repository_root or repository_root_from_module(),
                registry_path=registry_path,
            )
    except (json.JSONDecodeError, IntegrityGateError) as error:
        response = _failure(str(error))
    output_stream.write(json.dumps(response, sort_keys=True, separators=(",", ":")) + "\n")
    output_stream.flush()
    return 0
