"""CLI for the repository-only external benchmark harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .core import ExternalBenchmarkError, evaluate_scenario, list_scenarios, load_scenario

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EXTERNAL_ROOT.parent
DEFAULT_SCENARIOS = EXTERNAL_ROOT / "scenarios"


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="S3 external benchmark correctness harness")
    parser.add_argument("--list", action="store_true", help="list available external benchmark scenarios")
    parser.add_argument("--scenario", help="scenario id to evaluate")
    parser.add_argument("--observation-file", type=Path, help="JSON observation produced for the external system run")
    parser.add_argument("--scenario-root", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--output-json", type=Path)
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


def main(argv: Sequence[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    scenario_root = args.scenario_root.resolve()

    if args.list:
        print(json.dumps(list_scenarios(scenario_root), indent=2, sort_keys=True))
        return 0

    if not args.scenario:
        raise SystemExit("--scenario is required unless --list is used")
    if args.observation_file is None:
        raise SystemExit("--observation-file is required")

    try:
        scenario = load_scenario(_scenario_path(scenario_root, args.scenario))
        observation = json.loads(args.observation_file.read_text(encoding="utf-8"))
        if not isinstance(observation, dict):
            raise ExternalBenchmarkError("observation file must contain a JSON object")
        result = evaluate_scenario(scenario, observation, repository_root=args.repository_root)
    except (OSError, json.JSONDecodeError, ExternalBenchmarkError) as error:
        raise SystemExit(str(error)) from error

    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload + "\n", encoding="utf-8", newline="\n")
    print(payload)
    return 0 if result["status"] == "PASS" else 1
