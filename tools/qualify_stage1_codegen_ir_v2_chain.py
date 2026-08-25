"""Run the prepared Stage1 IR-v2 native candidate gates in sequence.

The chain is read-only with respect to the canonical compiler source. It first
qualifies compaction capacity. Only on a real PASS does it qualify the packed
parameter lane. If parameters pass, it also computes the next-phase local/value
budget directly from that native audit. It never promotes source, starts
Stage2/Stage3, or claims self-hosting.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.plan_stage1_codegen_ir_v2_next import (
    DEFAULT_REPORT as DEFAULT_NEXT_PHASE_REPORT,
    build_plan as build_next_phase_plan,
)
from tools.qualify_stage1_codegen_ir_v2_capacity import (
    DEFAULT_REPORT as DEFAULT_CAPACITY_REPORT,
    qualify as qualify_capacity,
)
from tools.qualify_stage1_codegen_ir_v2_parameters import (
    DEFAULT_REPORT as DEFAULT_PARAMETER_REPORT,
    qualify as qualify_parameters,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHAIN_REPORT = (
    ROOT
    / "reports"
    / "selfhost"
    / "stage1"
    / "codegen-ir-v2-native-chain.json"
)


def run_chain(
    *,
    capacity_report_path: Path,
    parameter_report_path: Path,
    next_phase_report_path: Path,
    chain_report_path: Path,
) -> dict[str, object]:
    capacity = qualify_capacity(
        report_path=capacity_report_path,
        run_contract_tests=True,
    )
    capacity_pass = (
        capacity.get("qualification", {}).get("capacity_candidate")
        == "PASS_NATIVE_CANDIDATE"
        and capacity.get("qualification", {}).get("canonical_commit_allowed") is True
    )

    parameter: dict[str, object] | None = None
    if capacity_pass:
        parameter = qualify_parameters(
            capacity_report_path=capacity_report_path,
            report_path=parameter_report_path,
        )

    parameter_pass = bool(
        parameter is not None
        and parameter.get("qualification", {}).get("parameter_ir_v2_candidate")
        == "PASS_NATIVE_CANDIDATE"
    )

    next_phase = build_next_phase_plan(parameter if parameter_pass else None)
    next_destination = next_phase_report_path.resolve()
    next_destination.parent.mkdir(parents=True, exist_ok=True)
    next_destination.write_text(
        json.dumps(next_phase, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    result = {
        "schema": "s3.selfhost.codegen-ir-v2-native-chain.v2",
        "canonical_source_mutated": False,
        "capacity_gate": {
            "status": "PASS" if capacity_pass else "FAIL",
            "report": str(capacity_report_path.resolve()),
        },
        "parameter_gate": {
            "status": (
                "PASS" if parameter_pass else "FAIL" if parameter is not None else "NOT_RUN"
            ),
            "report": str(parameter_report_path.resolve()),
        },
        "next_phase_budget": {
            "status": next_phase["status"],
            "local_ir_v2_start_allowed": next_phase["local_ir_v2_start_allowed"],
            "report": str(next_destination),
        },
        "chain_status": (
            "PASS_THROUGH_PARAMETER_CANDIDATE"
            if capacity_pass and parameter_pass
            else "BLOCKED_AT_PARAMETER_CANDIDATE"
            if capacity_pass
            else "BLOCKED_AT_CAPACITY_CANDIDATE"
        ),
        "canonical_commit_allowed": False,
        "canonical_commit_reason": "Candidate chain intentionally never mutates/promotes the canonical source. Review native reports first.",
        "general_emitter": "BLOCKED_IR_V2_INCOMPLETE",
        "self_emit": "NOT_STARTED",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }

    destination = chain_report_path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capacity-report", type=Path, default=DEFAULT_CAPACITY_REPORT)
    parser.add_argument("--parameter-report", type=Path, default=DEFAULT_PARAMETER_REPORT)
    parser.add_argument("--next-phase-report", type=Path, default=DEFAULT_NEXT_PHASE_REPORT)
    parser.add_argument("--chain-report", type=Path, default=DEFAULT_CHAIN_REPORT)
    args = parser.parse_args(argv)

    result = run_chain(
        capacity_report_path=args.capacity_report,
        parameter_report_path=args.parameter_report,
        next_phase_report_path=args.next_phase_report,
        chain_report_path=args.chain_report,
    )
    print(f"CHAIN_REPORT={args.chain_report.resolve()}")
    print(f"CAPACITY_GATE={result['capacity_gate']['status']}")
    print(f"PARAMETER_GATE={result['parameter_gate']['status']}")
    print(f"NEXT_PHASE_BUDGET={result['next_phase_budget']['status']}")
    print(f"LOCAL_IR_V2_START_ALLOWED={result['next_phase_budget']['local_ir_v2_start_allowed']}")
    print(f"CHAIN_STATUS={result['chain_status']}")
    print("CANONICAL_SOURCE_MUTATED=False")
    print("STAGE2=NOT_STARTED")
    print("STAGE3=NOT_STARTED")
    return 0 if result["chain_status"] == "PASS_THROUGH_PARAMETER_CANDIDATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
