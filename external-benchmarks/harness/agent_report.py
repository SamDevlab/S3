"""Minimal safe recall-report contract for Agent Memory V1 runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import ExternalBenchmarkError

AGENT_REPORT_SCHEMA_VERSION = "1.0.0"
MAX_AGENT_REPORT_BYTES = 16 * 1024
_ALLOWED_FIELDS = {"schema_version", "reported_invariants"}


def load_agent_report(path: Path) -> dict[str, Any]:
    """Load a bounded, transcript-free agent recall report."""

    try:
        size = path.stat().st_size
    except OSError as error:
        raise ExternalBenchmarkError("agent report is unavailable") from error
    if size > MAX_AGENT_REPORT_BYTES:
        raise ExternalBenchmarkError("agent report exceeds the size limit")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ExternalBenchmarkError("agent report could not be read") from error
    except json.JSONDecodeError as error:
        raise ExternalBenchmarkError("agent report is not valid JSON") from error
    if not isinstance(document, dict):
        raise ExternalBenchmarkError("agent report must be a JSON object")
    extras = sorted(set(document).difference(_ALLOWED_FIELDS))
    if extras:
        raise ExternalBenchmarkError(
            "agent report contains forbidden fields: " + ", ".join(extras)
        )
    if document.get("schema_version") != AGENT_REPORT_SCHEMA_VERSION:
        raise ExternalBenchmarkError("unsupported agent report schema")
    values = document.get("reported_invariants")
    if (
        not isinstance(values, list)
        or any(not isinstance(item, str) or not item for item in values)
    ):
        raise ExternalBenchmarkError("agent report reported_invariants must be a string list")
    if len(values) != len(set(values)):
        raise ExternalBenchmarkError("agent report reported_invariants must be unique")
    return {
        "schema_version": AGENT_REPORT_SCHEMA_VERSION,
        "reported_invariants": sorted(values),
    }
