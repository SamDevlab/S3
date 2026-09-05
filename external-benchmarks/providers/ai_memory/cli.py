"""CLI for the optional AI-MEMORY Agent Memory V1 adapter."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Sequence

from .client import AiMemoryClient, AiMemoryConfig, AiMemoryProviderError
from .runner import build_managed_run_command, execute_managed_run, workstream_name_from_plan

_ALLOWED_PLAN_PROVIDERS = {"ai-memory", "ai-memory+s3-integrity-gate"}


def _load_plan(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise AiMemoryProviderError("run plan could not be read") from error
    except json.JSONDecodeError as error:
        raise AiMemoryProviderError("run plan is not valid JSON") from error
    if not isinstance(document, dict):
        raise AiMemoryProviderError("run plan must be a JSON object")
    if document.get("campaign_id") != "agent-memory-v1":
        raise AiMemoryProviderError("AI-MEMORY adapter accepts only agent-memory-v1 plans")
    provider = document.get("provider")
    if not isinstance(provider, dict) or provider.get("id") not in _ALLOWED_PLAN_PROVIDERS:
        raise AiMemoryProviderError("run plan is not an AI-MEMORY provider arm")
    if not isinstance(document.get("scenarios"), list):
        raise AiMemoryProviderError("run plan scenarios are missing")
    return document


def _require_scenario(plan: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    matches = [
        item
        for item in plan["scenarios"]
        if isinstance(item, dict) and item.get("scenario_id") == scenario_id
    ]
    if len(matches) != 1:
        raise AiMemoryProviderError(f"scenario is not uniquely present in run plan: {scenario_id}")
    return matches[0]


def _emit(document: dict[str, object], output_json: Path | None = None) -> None:
    payload = json.dumps(document, indent=2, sort_keys=True, allow_nan=False)
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(payload + "\n", encoding="utf-8", newline="\n")
    print(payload)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Optional AI-MEMORY adapter for S3 Agent Memory V1"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe = subparsers.add_parser("probe", help="probe documented read-only AI-MEMORY API")
    probe.add_argument("--server-url")
    probe.add_argument("--workspace", required=True)
    probe.add_argument("--project", required=True)
    probe.add_argument("--timeout", type=float, default=5.0)
    probe.add_argument("--search-query")
    probe.add_argument("--output-json", type=Path)

    for name, help_text in (
        ("command", "print the managed ai-memory run argv without executing it"),
        ("run", "explicitly launch a managed agent through the host ai-memory executable"),
    ):
        launch = subparsers.add_parser(name, help=help_text)
        launch.add_argument("--plan-file", type=Path, required=True)
        launch.add_argument("--scenario", required=True)
        launch.add_argument("--workspace", required=True)
        launch.add_argument("--project", required=True)
        launch.add_argument("--phase", choices=("new", "resume"), required=True)
        launch.add_argument("--harness", required=True)
        launch.add_argument(
            "--ai-memory-executable",
            default=os.environ.get("AI_MEMORY_BIN", "ai-memory"),
        )
        launch.add_argument("--native-arg", action="append", default=[])
        launch.add_argument(
            "--allow-linked-session",
            action="store_true",
            help="do not pass --fresh; invalid for controlled cross-session/cross-agent runs",
        )
        if name == "run":
            launch.add_argument("--worktree", type=Path, required=True)
            launch.add_argument("--process-metadata-file", type=Path)
            launch.add_argument("--phase-name")
            launch.add_argument("--agent-provider")
            launch.add_argument("--agent-model")
            launch.add_argument("--agent-harness")
            launch.add_argument(
                "--execute",
                action="store_true",
                help="required acknowledgement before starting the external agent process",
            )
    return parser


def _probe(args: argparse.Namespace) -> int:
    config = AiMemoryConfig.from_environment(
        server_url=args.server_url,
        timeout_seconds=args.timeout,
    )
    client = AiMemoryClient(config)
    result = client.probe(workspace=args.workspace, project=args.project)
    if args.search_query:
        result["diagnostics"] = {
            "search_hit_count": client.search_count(
                workspace=args.workspace,
                project=args.project,
                query=args.search_query,
            )
        }
    _emit(result, args.output_json)
    return 0


def _launch(args: argparse.Namespace) -> int:
    plan = _load_plan(args.plan_file)
    scenario = _require_scenario(plan, args.scenario)
    mode = scenario.get("mode")
    if args.allow_linked_session and mode in {"cross-session", "cross-agent"}:
        raise AiMemoryProviderError(
            "controlled cross-session/cross-agent runs require --fresh to prevent native transcript reuse"
        )
    workstream = workstream_name_from_plan(plan, args.scenario)
    launch = build_managed_run_command(
        executable=args.ai_memory_executable,
        workspace=args.workspace,
        project=args.project,
        workstream=workstream,
        phase=args.phase,
        harness=args.harness,
        native_args=tuple(args.native_arg),
        fresh=not args.allow_linked_session,
    )
    if args.command == "command":
        _emit(launch.as_document())
        return 0
    if not args.execute:
        raise AiMemoryProviderError("run requires explicit --execute acknowledgement")
    agent = None
    if args.process_metadata_file is not None:
        if not all(
            isinstance(value, str) and value
            for value in (args.agent_provider, args.agent_model, args.agent_harness)
        ):
            raise AiMemoryProviderError(
                "agent identity is required with --process-metadata-file"
            )
        if not isinstance(args.phase_name, str) or not args.phase_name:
            raise AiMemoryProviderError("--phase-name is required with process metadata")
        agent = {
            "provider": args.agent_provider,
            "model": args.agent_model,
            "harness": args.agent_harness,
        }
    return execute_managed_run(
        launch,
        worktree=args.worktree,
        process_metadata_file=args.process_metadata_file,
        scenario_id=args.scenario if args.process_metadata_file is not None else None,
        phase=args.phase_name if args.process_metadata_file is not None else None,
        agent=agent,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    try:
        if args.command == "probe":
            return _probe(args)
        return _launch(args)
    except AiMemoryProviderError as error:
        raise SystemExit(str(error)) from error
