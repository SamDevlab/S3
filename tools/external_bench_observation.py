"""Materialize safe external benchmark observations from a deterministic run plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_ROOT = REPOSITORY_ROOT / "external-benchmarks"
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.agent_report import load_agent_report  # noqa: E402
from harness.core import ExternalBenchmarkError  # noqa: E402
from harness.observation import materialize_observation  # noqa: E402
from harness.runbook import handoff_agents_from_runbook  # noqa: E402


def _load_object(path: Path, name: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ExternalBenchmarkError(f"{name} could not be read") from error
    except json.JSONDecodeError as error:
        raise ExternalBenchmarkError(f"{name} is not valid JSON") from error
    if not isinstance(document, dict):
        raise ExternalBenchmarkError(f"{name} must be a JSON object")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize one S3 external benchmark observation from a run plan"
    )
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--reported-invariant", action="append", default=[])
    parser.add_argument("--agent-report-file", type=Path)
    parser.add_argument("--runbook-file", type=Path)
    parser.add_argument("--process-metadata-dir", type=Path)
    parser.add_argument("--source-agent-file", type=Path)
    parser.add_argument("--target-agent-file", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        if args.agent_report_file is not None and args.reported_invariant:
            raise ExternalBenchmarkError(
                "--agent-report-file and --reported-invariant are mutually exclusive"
            )
        if args.runbook_file is not None and (
            args.source_agent_file is not None or args.target_agent_file is not None
        ):
            raise ExternalBenchmarkError(
                "--runbook-file cannot be combined with explicit source/target agent files"
            )

        plan = _load_object(args.plan_file, "run plan")
        reported = list(args.reported_invariant)
        if args.agent_report_file is not None:
            reported = list(load_agent_report(args.agent_report_file)["reported_invariants"])

        source: dict[str, Any] | None = None
        target: dict[str, Any] | None = None
        if args.runbook_file is not None:
            runbook = _load_object(args.runbook_file, "runbook")
            handoff = handoff_agents_from_runbook(runbook, args.scenario)
            if handoff is not None:
                source, target = handoff
        else:
            source = (
                _load_object(args.source_agent_file, "source agent")
                if args.source_agent_file
                else None
            )
            target = (
                _load_object(args.target_agent_file, "target agent")
                if args.target_agent_file
                else None
            )

        observation = materialize_observation(
            plan,
            scenario_id=args.scenario,
            reported_invariants=reported,
            source_agent=source,
            target_agent=target,
            process_metadata_dir=args.process_metadata_dir,
            runbook=runbook if args.runbook_file is not None else None,
        )
        payload = json.dumps(observation, indent=2, sort_keys=True, allow_nan=False)
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload + "\n", encoding="utf-8", newline="\n")
        print(payload)
        return 0
    except ExternalBenchmarkError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    raise SystemExit(main())
