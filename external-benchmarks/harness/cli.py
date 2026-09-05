"""CLI for the repository-only external benchmark harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .campaign import aggregate_campaign, list_campaigns, load_campaign
from .comparison import compare_campaign
from .core import ExternalBenchmarkError, evaluate_scenario, list_scenarios, load_scenario
from .plan import build_run_plan
from .report import render_comparison_markdown
from .task_pack import (
    TaskPackError,
    attach_task_checks,
    load_task_pack,
    task_for_scenario,
    validate_task_artifacts,
)

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EXTERNAL_ROOT.parent
DEFAULT_SCENARIOS = EXTERNAL_ROOT / "scenarios"
DEFAULT_CAMPAIGNS = EXTERNAL_ROOT / "campaigns"
DEFAULT_TASK_PACK = EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json"


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="S3 external benchmark correctness harness")
    parser.add_argument("--list", action="store_true", help="list available external benchmark scenarios")
    parser.add_argument(
        "--list-campaigns",
        action="store_true",
        help="list available external benchmark campaigns",
    )
    parser.add_argument("--scenario", help="scenario id to evaluate")
    parser.add_argument("--campaign", help="campaign id to aggregate, compare, or plan")
    parser.add_argument("--prepare-run", action="store_true", help="emit a deterministic provider/repetition run plan")
    parser.add_argument(
        "--observation-file",
        type=Path,
        help="JSON observation produced for one external system run",
    )
    parser.add_argument(
        "--result-dir",
        type=Path,
        help="directory containing one isolated scenario result per campaign scenario",
    )
    parser.add_argument(
        "--compare-root",
        type=Path,
        help="root containing provider/run-N/campaign.json results",
    )
    parser.add_argument("--provider")
    parser.add_argument("--provider-version")
    parser.add_argument("--repetition", type=int)
    parser.add_argument("--s3-commit")
    parser.add_argument("--agent-provider")
    parser.add_argument("--agent-model")
    parser.add_argument("--agent-harness")
    parser.add_argument("--agent-harness-version")
    parser.add_argument("--tool-permissions-profile")
    parser.add_argument("--task-protocol-version")
    parser.add_argument(
        "--repetitions",
        type=int,
        help="override campaign recommended repetitions for comparison",
    )
    parser.add_argument("--scenario-root", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--campaign-root", type=Path, default=DEFAULT_CAMPAIGNS)
    parser.add_argument("--task-pack-file", type=Path, default=DEFAULT_TASK_PACK)
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    return parser


def _scenario_path(root: Path, scenario_id: str) -> Path:
    candidates = []
    for path in sorted(root.glob("*.json")):
        scenario = load_scenario(path)
        if scenario["scenario_id"] == scenario_id:
            candidates.append(path)
    if not candidates:
        raise ExternalBenchmarkError(f"unknown scenario: {scenario_id}")
    if len(candidates) != 1:
        raise ExternalBenchmarkError(f"duplicate scenario id: {scenario_id}")
    return candidates[0]


def _campaign_path(root: Path, campaign_id: str) -> Path:
    candidates = []
    for path in sorted(root.glob("*.json")):
        campaign = load_campaign(path)
        if campaign["campaign_id"] == campaign_id:
            candidates.append(path)
    if not candidates:
        raise ExternalBenchmarkError(f"unknown campaign: {campaign_id}")
    if len(candidates) != 1:
        raise ExternalBenchmarkError(f"duplicate campaign id: {campaign_id}")
    return candidates[0]


def _write_document(document: dict[str, object], output_json: Path | None) -> None:
    payload = json.dumps(document, indent=2, sort_keys=True, allow_nan=False)
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(payload + "\n", encoding="utf-8", newline="\n")
    print(payload)


def _emit(
    result: dict[str, object],
    output_json: Path | None,
    *,
    output_markdown: Path | None = None,
    markdown: str | None = None,
) -> int:
    _write_document(result, output_json)
    if output_markdown:
        if markdown is None:
            raise ExternalBenchmarkError(
                "--output-markdown is supported only for campaign comparison"
            )
        output_markdown.parent.mkdir(parents=True, exist_ok=True)
        output_markdown.write_text(markdown, encoding="utf-8", newline="\n")
    return 0 if result["status"] in {"PASS", "VALID_PASS"} else 1


def _required_plan_argument(args: argparse.Namespace, name: str) -> str:
    value = getattr(args, name)
    if not isinstance(value, str) or not value:
        raise ExternalBenchmarkError(f"--{name.replace('_', '-')} is required with --prepare-run")
    return value


def _subject_commit(campaign: dict[str, object]) -> str | None:
    protocol = campaign.get("protocol")
    if not isinstance(protocol, dict):
        return None
    value = protocol.get("subject_commit")
    return value if isinstance(value, str) and value else None


def _prepare_run(args: argparse.Namespace, campaign: dict[str, object]) -> int:
    if args.result_dir is not None or args.compare_root is not None or args.scenario:
        raise ExternalBenchmarkError(
            "--prepare-run cannot be combined with --scenario, --result-dir, or --compare-root"
        )
    if args.output_markdown is not None:
        raise ExternalBenchmarkError("--output-markdown is not valid with --prepare-run")
    if args.repetition is None:
        raise ExternalBenchmarkError("--repetition is required with --prepare-run")
    s3_commit = args.s3_commit or _subject_commit(campaign)
    if not isinstance(s3_commit, str) or not s3_commit:
        raise ExternalBenchmarkError(
            "--s3-commit is required when the campaign does not pin protocol.subject_commit"
        )

    plan = build_run_plan(
        campaign,
        provider_id=_required_plan_argument(args, "provider"),
        provider_version=_required_plan_argument(args, "provider_version"),
        repetition=args.repetition,
        s3_commit=s3_commit,
        agent_provider=_required_plan_argument(args, "agent_provider"),
        agent_model=_required_plan_argument(args, "agent_model"),
        agent_harness=_required_plan_argument(args, "agent_harness"),
        agent_harness_version=_required_plan_argument(args, "agent_harness_version"),
        tool_permissions_profile=_required_plan_argument(args, "tool_permissions_profile"),
        task_protocol_version=args.task_protocol_version,
    )
    for scenario in plan["scenarios"]:
        template = EXTERNAL_ROOT / str(scenario["template"])
        if not template.is_file():
            raise ExternalBenchmarkError(f"run-plan template is missing: {scenario['template']}")
    _write_document(plan, args.output_json)
    return 0


def _attach_agent_memory_task_checks(
    result: dict[str, object],
    *,
    scenario_id: str,
    observation: dict[str, object],
    task_pack_file: Path,
    repository_root: Path,
) -> None:
    task_pack = load_task_pack(task_pack_file)
    rows = task_pack.get("scenarios")
    if not isinstance(rows, list):
        raise TaskPackError("task pack scenarios are invalid")
    if not any(isinstance(row, dict) and row.get("scenario_id") == scenario_id for row in rows):
        return
    task = task_for_scenario(task_pack, scenario_id)
    execution = observation.get("execution")
    if not isinstance(execution, dict):
        raise TaskPackError("Agent Memory V1 observation requires execution metadata")
    base_commit = execution.get("s3_commit")
    if not isinstance(base_commit, str) or not base_commit:
        raise TaskPackError("Agent Memory V1 observation requires execution.s3_commit")
    checks = validate_task_artifacts(
        task,
        repository_root=repository_root,
        base_commit=base_commit,
    )
    attach_task_checks(result, checks)


def main(argv: Sequence[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    scenario_root = args.scenario_root.resolve()
    campaign_root = args.campaign_root.resolve()

    if args.list and args.list_campaigns:
        raise SystemExit("--list and --list-campaigns are mutually exclusive")
    if args.list:
        print(json.dumps(list_scenarios(scenario_root), indent=2, sort_keys=True))
        return 0
    if args.list_campaigns:
        print(json.dumps(list_campaigns(campaign_root), indent=2, sort_keys=True))
        return 0
    if args.scenario and args.campaign:
        raise SystemExit("--scenario and --campaign are mutually exclusive")
    if args.output_markdown and not args.compare_root:
        raise SystemExit("--output-markdown requires --compare-root")

    try:
        if args.prepare_run:
            if not args.campaign:
                raise ExternalBenchmarkError("--campaign is required with --prepare-run")
            if args.repetitions is not None:
                raise ExternalBenchmarkError("--repetitions is not valid with --prepare-run")
            campaign = load_campaign(_campaign_path(campaign_root, args.campaign))
            return _prepare_run(args, campaign)

        plan_only_values = (
            args.provider,
            args.provider_version,
            args.repetition,
            args.s3_commit,
            args.agent_provider,
            args.agent_model,
            args.agent_harness,
            args.agent_harness_version,
            args.tool_permissions_profile,
            args.task_protocol_version,
        )
        if any(value is not None for value in plan_only_values):
            raise ExternalBenchmarkError("run-plan arguments require --prepare-run")

        if args.campaign:
            if args.result_dir is not None and args.compare_root is not None:
                raise ExternalBenchmarkError(
                    "--result-dir and --compare-root are mutually exclusive"
                )
            campaign = load_campaign(_campaign_path(campaign_root, args.campaign))
            if args.compare_root is not None:
                result = compare_campaign(
                    campaign,
                    comparison_root=args.compare_root,
                    repetitions=args.repetitions,
                )
                return _emit(
                    result,
                    args.output_json,
                    output_markdown=args.output_markdown,
                    markdown=render_comparison_markdown(result),
                )
            if args.result_dir is None:
                raise SystemExit("--result-dir or --compare-root is required with --campaign")
            result = aggregate_campaign(campaign, result_dir=args.result_dir)
            return _emit(result, args.output_json)

        if not args.scenario:
            raise SystemExit("--scenario or --campaign is required unless a list option is used")
        if args.observation_file is None:
            raise SystemExit("--observation-file is required with --scenario")
        if args.repetitions is not None:
            raise SystemExit("--repetitions is valid only with --campaign --compare-root")
        observation = json.loads(args.observation_file.read_text(encoding="utf-8"))
        if not isinstance(observation, dict):
            raise ExternalBenchmarkError("observation file must contain a JSON object")
        scenario = load_scenario(_scenario_path(scenario_root, args.scenario))
        result = evaluate_scenario(
            scenario,
            observation,
            repository_root=args.repository_root,
        )
        _attach_agent_memory_task_checks(
            result,
            scenario_id=args.scenario,
            observation=observation,
            task_pack_file=args.task_pack_file,
            repository_root=args.repository_root,
        )
        return _emit(result, args.output_json)
    except (OSError, json.JSONDecodeError, ExternalBenchmarkError, TaskPackError) as error:
        raise SystemExit(str(error)) from error
