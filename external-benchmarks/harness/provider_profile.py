"""Safe provider-arm profiles for Agent Memory V1."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .core import ExternalBenchmarkError

PROFILE_SCHEMA_VERSION = "1.0.0"
_AGENT_MEMORY_PROVIDERS = {
    "no-memory",
    "context-only",
    "ai-memory",
    "ai-memory+s3-integrity-gate",
}


def _registry_path(repository_root: Path) -> Path:
    return repository_root / "external-benchmarks" / "invariants" / "agent-memory-v1.json"


def _registry_identity(repository_root: Path) -> tuple[str, str]:
    path = _registry_path(repository_root)
    try:
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExternalBenchmarkError("Agent Memory integrity registry is unavailable") from error
    if not isinstance(document, dict):
        raise ExternalBenchmarkError("Agent Memory integrity registry must be a JSON object")
    version = document.get("schema_version")
    if not isinstance(version, str) or not version:
        raise ExternalBenchmarkError("Agent Memory integrity registry schema is invalid")
    return version, hashlib.sha256(raw).hexdigest()


def build_provider_profile(provider_id: str, *, repository_root: Path) -> dict[str, Any]:
    """Build the safe experimental profile for one Agent Memory provider arm."""

    if provider_id not in _AGENT_MEMORY_PROVIDERS:
        raise ExternalBenchmarkError(f"unsupported Agent Memory provider profile: {provider_id}")
    if provider_id == "no-memory":
        return {"schema_version": PROFILE_SCHEMA_VERSION, "memory_mode": "none"}
    if provider_id == "context-only":
        return {"schema_version": PROFILE_SCHEMA_VERSION, "memory_mode": "context-only"}
    if provider_id == "ai-memory":
        return {
            "schema_version": PROFILE_SCHEMA_VERSION,
            "memory_mode": "ai-memory",
            "integrity_gate": {"enabled": False},
        }
    registry_version, registry_sha256 = _registry_identity(repository_root.resolve())
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "memory_mode": "ai-memory",
        "integrity_gate": {
            "enabled": True,
            "registry_schema_version": registry_version,
            "registry_sha256": registry_sha256,
        },
    }


def sanitize_provider_profile(value: object, *, provider_id: str) -> dict[str, Any]:
    """Validate and copy only the safe Agent Memory provider-profile fields."""

    if not isinstance(value, dict):
        raise ExternalBenchmarkError("provider_profile must be a JSON object")
    if value.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ExternalBenchmarkError("provider_profile schema is unsupported")
    mode = value.get("memory_mode")
    expected_mode = {
        "no-memory": "none",
        "context-only": "context-only",
        "ai-memory": "ai-memory",
        "ai-memory+s3-integrity-gate": "ai-memory",
    }.get(provider_id)
    if expected_mode is None or mode != expected_mode:
        raise ExternalBenchmarkError("provider_profile memory mode does not match provider arm")

    result: dict[str, Any] = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "memory_mode": mode,
    }
    gate = value.get("integrity_gate")
    if provider_id in {"no-memory", "context-only"}:
        if gate is not None:
            raise ExternalBenchmarkError("provider_profile integrity gate is invalid for this arm")
        return result
    if not isinstance(gate, dict):
        raise ExternalBenchmarkError("provider_profile.integrity_gate must be an object")
    expected_enabled = provider_id == "ai-memory+s3-integrity-gate"
    if gate.get("enabled") is not expected_enabled:
        raise ExternalBenchmarkError("provider_profile integrity gate state does not match provider arm")
    clean_gate: dict[str, Any] = {"enabled": expected_enabled}
    if expected_enabled:
        version = gate.get("registry_schema_version")
        digest = gate.get("registry_sha256")
        if not isinstance(version, str) or not version:
            raise ExternalBenchmarkError("provider_profile registry schema version is invalid")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise ExternalBenchmarkError("provider_profile registry sha256 is invalid")
        clean_gate["registry_schema_version"] = version
        clean_gate["registry_sha256"] = digest
    result["integrity_gate"] = clean_gate
    return result


def provider_profile_identity(value: Mapping[str, Any]) -> str:
    """Canonical identity used for within-provider consistency checks."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
