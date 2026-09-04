"""Managed AI-MEMORY launcher for Agent Memory V1.

This module never imports AI-MEMORY internals. It builds the documented host CLI
command and executes it only when the caller explicitly requests execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .client import AiMemoryProviderError, validate_scope_name
from harness.timeout_policy import load_timeout_policy, run_controlled_process

_HARNESS_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _harness(value: str) -> str:
    if not isinstance(value, str) or not _HARNESS_RE.fullmatch(value):
        raise AiMemoryProviderError("harness must be a portable executable alias")
    return value


def _provider_slug(provider_id: str) -> str:
    slug = provider_id.lower().replace("+", "-")
    slug = re.sub(r"[^a-z0-9._-]+", "-", slug).strip("-._")
    if not slug:
        raise AiMemoryProviderError("provider id cannot be converted to a workstream name")
    return slug


def _scenario_slug(scenario_id: str) -> str:
    slug = scenario_id.lower()
    if slug.startswith("memory."):
        slug = slug[len("memory.") :]
    if slug.endswith(".v1"):
        slug = slug[: -len(".v1")]
    slug = re.sub(r"[^a-z0-9._-]+", "-", slug).replace(".", "-").strip("-_")
    if not slug:
        raise AiMemoryProviderError("scenario id cannot be converted to a workstream name")
    return slug


def workstream_name_from_plan(plan: Mapping[str, Any], scenario_id: str) -> str:
    """Create a deterministic provider-isolated workstream name for one scenario."""

    provider = plan.get("provider")
    execution = plan.get("execution")
    if not isinstance(provider, dict) or not isinstance(execution, dict):
        raise AiMemoryProviderError("run plan must contain provider and execution objects")
    provider_id = provider.get("id")
    repetition = execution.get("repetition")
    if not isinstance(provider_id, str) or not provider_id:
        raise AiMemoryProviderError("run plan provider.id is invalid")
    if not isinstance(repetition, int) or isinstance(repetition, bool) or repetition < 1:
        raise AiMemoryProviderError("run plan execution.repetition is invalid")
    return validate_scope_name(
        f"s3-amv1-{_provider_slug(provider_id)}-r{repetition}-{_scenario_slug(scenario_id)}",
        "workstream",
    )


@dataclass(frozen=True)
class AiMemoryLaunch:
    """Safe launch description. It contains no token, endpoint, transcript, or prompt."""

    argv: tuple[str, ...]
    phase: str
    workstream: str

    def as_document(self) -> dict[str, object]:
        return {
            "provider": "ai-memory",
            "phase": self.phase,
            "workstream": self.workstream,
            "argv": list(self.argv),
        }


def build_managed_run_command(
    *,
    executable: str,
    workspace: str,
    project: str,
    workstream: str,
    phase: str,
    harness: str,
    native_args: Sequence[str] = (),
    fresh: bool = True,
) -> AiMemoryLaunch:
    """Build documented `ai-memory run` argv without invoking a subprocess."""

    if not isinstance(executable, str) or not executable:
        raise AiMemoryProviderError("AI-MEMORY executable must be a non-empty string")
    if phase not in {"new", "resume"}:
        raise AiMemoryProviderError("phase must be 'new' or 'resume'")
    if any(not isinstance(item, str) or not item for item in native_args):
        raise AiMemoryProviderError("native harness arguments must be non-empty strings")

    argv = [
        executable,
        "run",
        "--workspace",
        validate_scope_name(workspace, "workspace"),
        "--project",
        validate_scope_name(project, "project"),
    ]
    if phase == "new":
        argv.extend(["--new", validate_scope_name(workstream, "workstream")])
    else:
        argv.extend(["--workstream", validate_scope_name(workstream, "workstream")])
    if fresh:
        argv.append("--fresh")
    argv.append(_harness(harness))
    argv.extend(native_args)
    return AiMemoryLaunch(argv=tuple(argv), phase=phase, workstream=workstream)


def execute_managed_run(launch: AiMemoryLaunch, *, worktree: Path) -> int:
    """Execute an interactive host harness without capturing or persisting its transcript."""

    worktree = worktree.resolve()
    if not worktree.is_dir():
        raise AiMemoryProviderError("AI-MEMORY launch worktree does not exist")
    result = run_controlled_process(
        list(launch.argv),
        cwd=worktree,
        policy=load_timeout_policy(),
    )
    return int(result.returncode)
