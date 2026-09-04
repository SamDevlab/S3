"""Versioned process-timeout policy for Agent Memory V1 live runs."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .core import ExternalBenchmarkError

TIMEOUT_POLICY_SCHEMA_VERSION = "1.0.0"
TIMEOUT_POLICY_ID = "windows-agent-memory-timeout-v1"
TIMEOUT_SECONDS = 1800
TIMEOUT_EXIT_CODE = 124
_POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / f"{TIMEOUT_POLICY_ID}.json"


@dataclass(frozen=True)
class TimeoutPolicy:
    policy_id: str
    timeout_seconds: float
    on_timeout: str
    dynamic_adjustment: bool

    def as_document(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "timeout_seconds": int(self.timeout_seconds)
            if self.timeout_seconds.is_integer()
            else self.timeout_seconds,
            "on_timeout": self.on_timeout,
            "dynamic_adjustment": self.dynamic_adjustment,
        }


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    timed_out: bool
    elapsed_seconds: float


def _require_policy(document: object) -> TimeoutPolicy:
    if not isinstance(document, dict):
        raise ExternalBenchmarkError("timeout policy must be a JSON object")
    if document.get("schema_version") != TIMEOUT_POLICY_SCHEMA_VERSION:
        raise ExternalBenchmarkError("unsupported timeout policy schema")
    if document.get("policy_id") != TIMEOUT_POLICY_ID:
        raise ExternalBenchmarkError("unexpected timeout policy id")
    if document.get("scope") != "agent-memory-v1" or document.get("platform") != "windows":
        raise ExternalBenchmarkError("timeout policy scope or platform is invalid")
    timeout = document.get("timeout_seconds")
    if timeout != TIMEOUT_SECONDS:
        raise ExternalBenchmarkError("timeout policy must freeze 1800 seconds")
    if document.get("on_timeout") != "INVALID_OPERATIONAL_RUN":
        raise ExternalBenchmarkError("timeout policy classification is invalid")
    if document.get("dynamic_adjustment") is not False:
        raise ExternalBenchmarkError("timeout policy must forbid dynamic adjustment")
    if document.get("unit") != "seconds" or not isinstance(document.get("applies_to"), str):
        raise ExternalBenchmarkError("timeout policy metadata is invalid")
    return TimeoutPolicy(
        policy_id=TIMEOUT_POLICY_ID,
        timeout_seconds=float(TIMEOUT_SECONDS),
        on_timeout="INVALID_OPERATIONAL_RUN",
        dynamic_adjustment=False,
    )


def load_timeout_policy(path: Path | None = None) -> TimeoutPolicy:
    policy_path = (path or _POLICY_PATH).resolve()
    try:
        document = json.loads(policy_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ExternalBenchmarkError("timeout policy could not be read") from error
    except json.JSONDecodeError as error:
        raise ExternalBenchmarkError("timeout policy is not valid JSON") from error
    return _require_policy(document)


def timeout_policy_document(policy: TimeoutPolicy | None = None) -> dict[str, object]:
    selected = policy or load_timeout_policy()
    return selected.as_document()


def _terminate_tree(process: subprocess.Popen[Any]) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
                timeout=30,
            )
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
    try:
        process.kill()
    except OSError:
        pass


def run_controlled_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    input_text: str | None = None,
    policy: TimeoutPolicy | None = None,
) -> ProcessResult:
    """Run one process under the frozen policy and kill its child tree on timeout."""

    selected = policy or load_timeout_policy()
    arguments = list(argv)
    if not arguments or any(not isinstance(item, str) or not item for item in arguments):
        raise ExternalBenchmarkError("controlled process argv is invalid")
    started = time.monotonic()
    try:
        process = subprocess.Popen(  # noqa: S603
            arguments,
            cwd=cwd,
            stdin=subprocess.PIPE if input_text is not None else None,
            shell=False,
            text=True,
        )
    except OSError as error:
        raise ExternalBenchmarkError("controlled process could not be started") from error
    try:
        process.communicate(input=input_text, timeout=selected.timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_tree(process)
        try:
            process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            _terminate_tree(process)
        elapsed = time.monotonic() - started
        return ProcessResult(
            returncode=TIMEOUT_EXIT_CODE,
            timed_out=True,
            elapsed_seconds=elapsed,
        )
    return ProcessResult(
        returncode=int(process.returncode),
        timed_out=False,
        elapsed_seconds=time.monotonic() - started,
    )
