"""Generate and execute provider-neutral Agent Memory V1 runbooks."""

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
from harness.runbook import build_runbook, execute_direct_step  # noqa: E402
from harness.task_pack import TaskPackError, load_task_pack  # noqa: E402

DEFAULT_TASK_PACK = EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json"
DEFAULT_SCENARIOS = EXTERNAL_ROOT / "scenarios"


def _object_file(path: Path, name: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ExternalBenchmarkError(f"{name} could not be read") from error
    except json.JSONDecodeError as error:
        raise ExternalBenchmarkError(f"{name} is not valid JSON") from error
    if not isinstance(value, dict):
        raise ExternalBenchmarkError(f"{name} must be a JSON object")
    return value


def _scenarios(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        scenario = load_scenario(path)
        scenario_id = str(scenario["scenario_id"])
        if scenario_id in result:
            raise ExternalBenchmarkError(f"duplicate scenario id: {scenario_id}")
        result[scenario_id] = scenario
    return result


def _find_step(runbook: dict[str, Any], scenario_id: str, step_id: str) -> dict[str, Any]:
    rows = runbook.get("scenarios")
    if not isinstance(rows, list):
        raise ExternalBenchmarkError("runbook scenarios are invalid")
    for raw in rows:
        if not isinstance(raw, dict) or raw.get("scenario_id") != scenario_id:
            continue
        steps = raw.get("steps")
        if not isinstance(steps, list):
            break
        matches = [step for step in steps if isinstance(step, dict) and step.get("id") == step_id]
        if len(matches) == 1:
            return matches[0]
    raise ExternalBenchmarkError("runbook step is not uniquely available")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent Memory V1 execution runbook utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--plan-file", type=Path, required=True)
    build.add_argument("--run-dir", type=Path, required=True)
    build.add_argument("--task-pack-file", type=Path, default=DEFAULT_TASK_PACK)
    build.add_argument("--scenario-root", type=Path, default=DEFAULT_SCENARIOS)
    build.add_argument("--direct-arg", action="append", default=[])
    build.add_argument("--target-direct-arg", action="append", default=[])
    build.add_argument("--target-agent-provider", required=True)
    build.add_argument("--target-agent-model", required=True)
    build.add_argument("--target-agent-harness", required=True)
    build.add_argument("--ai-memory-executable", default="ai-memory")
    build.add_argument("--ai-memory-workspace", default="s3bench")
    build.add_argument("--ai-memory-project", default="s3-agent-memory-v1")
    build.add_argument("--ai-memory-native-arg", action="append", default=[])
    build.add_argument("--target-ai-memory-native-arg", action="append", default=[])

    execute = subparsers.add_parser("execute-direct")
    execute.add_argument("--runbook-file", type=Path, required=True)
    execute.add_argument("--scenario", required=True)
    execute.add_argument("--step", required=True)
    execute.add_argument("--run-dir", type=Path, required=True)
    execute.add_argument("--worktree-root", type=Path, required=True)
    execute.add_argument("--process-metadata-file", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            plan = _object_file(args.plan_file, "run plan")
            task_pack = load_task_pack(args.task_pack_file)
            runbook = build_runbook(
                plan,
                scenarios=_scenarios(args.scenario_root),
                task_pack=task_pack,
                run_dir=args.run_dir,
                direct_argv=args.direct_arg,
                target_agent={
                    "provider": args.target_agent_provider,
                    "model": args.target_agent_model,
                    "harness": args.target_agent_harness,
                },
                target_direct_argv=args.target_direct_arg or None,
                ai_memory_executable=args.ai_memory_executable,
                ai_memory_workspace=args.ai_memory_workspace,
                ai_memory_project=args.ai_memory_project,
                ai_memory_native_args=args.ai_memory_native_arg,
                target_ai_memory_native_args=args.target_ai_memory_native_arg or None,
            )
            print(json.dumps(runbook, indent=2, sort_keys=True, allow_nan=False))
            return 0

        runbook = _object_file(args.runbook_file, "runbook")
        step = _find_step(runbook, args.scenario, args.step)
        return execute_direct_step(
            step,
            run_dir=args.run_dir,
            worktree_root=args.worktree_root,
            process_metadata_file=args.process_metadata_file,
            scenario_id=args.scenario,
            phase=args.step,
        )
    except (ExternalBenchmarkError, TaskPackError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    raise SystemExit(main())
