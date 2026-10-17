"""Render Agent Memory V1 phase prompts and validate task artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_ROOT = REPOSITORY_ROOT / "external-benchmarks"
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.core import ExternalBenchmarkError, load_scenario  # noqa: E402
from harness.task_pack import (  # noqa: E402
    TaskPackError,
    load_task_pack,
    render_phase_prompt,
    task_for_scenario,
    validate_task_artifacts,
)

DEFAULT_TASK_PACK = EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json"
DEFAULT_SCENARIOS = EXTERNAL_ROOT / "scenarios"


def _load_object(path: Path, name: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise TaskPackError(f"{name} could not be read") from error
    except json.JSONDecodeError as error:
        raise TaskPackError(f"{name} is not valid JSON") from error
    if not isinstance(document, dict):
        raise TaskPackError(f"{name} must be a JSON object")
    return document


def _scenario_path(root: Path, scenario_id: str) -> Path:
    matches: list[Path] = []
    for path in sorted(root.glob("*.json")):
        scenario = load_scenario(path)
        if scenario.get("scenario_id") == scenario_id:
            matches.append(path)
    if len(matches) != 1:
        raise TaskPackError(f"scenario is not uniquely available: {scenario_id}")
    return matches[0]


def _add_common(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("--plan-file", type=Path, required=True)
    subparser.add_argument("--scenario", required=True)
    subparser.add_argument("--task-pack-file", type=Path, default=DEFAULT_TASK_PACK)
    subparser.add_argument("--scenario-root", type=Path, default=DEFAULT_SCENARIOS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent Memory V1 task-pack utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser("render")
    _add_common(render)
    render.add_argument("--phase", choices=("a", "b"), required=True)
    render.add_argument("--output-file", type=Path, required=True)

    validate = subparsers.add_parser("validate")
    _add_common(validate)
    validate.add_argument("--repository-root", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        plan = _load_object(args.plan_file, "run plan")
        task_pack = load_task_pack(args.task_pack_file)
        scenario = load_scenario(_scenario_path(args.scenario_root, args.scenario))
        task = task_for_scenario(task_pack, args.scenario)
        if args.command == "render":
            profile = plan.get("provider_profile")
            if not isinstance(profile, dict):
                raise TaskPackError("run plan provider_profile is invalid")
            prompt = render_phase_prompt(
                task_pack,
                scenario,
                profile,
                phase=args.phase,
            )
            args.output_file.parent.mkdir(parents=True, exist_ok=True)
            args.output_file.write_text(prompt, encoding="utf-8", newline="\n")
            print(prompt, end="")
            return 0

        execution = plan.get("execution")
        if not isinstance(execution, dict):
            raise TaskPackError("run plan execution is invalid")
        base_commit = execution.get("s3_commit")
        if not isinstance(base_commit, str) or not base_commit:
            raise TaskPackError("run plan execution.s3_commit is invalid")
        checks = validate_task_artifacts(
            task,
            repository_root=args.repository_root,
            base_commit=base_commit,
        )
        document = {
            "scenario_id": args.scenario,
            "status": "PASS" if all(row["passed"] for row in checks) else "FAIL",
            "checks": checks,
        }
        print(json.dumps(document, indent=2, sort_keys=True))
        return 0 if document["status"] == "PASS" else 1
    except (ExternalBenchmarkError, TaskPackError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    raise SystemExit(main())
