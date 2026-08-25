"""Run prepared Stage1 IR-v2 candidate gates in fail-closed sequence.

The chain is read-only with respect to the canonical compiler source. It first
runs static storage/initializer preflight, then qualifies compaction capacity,
then (only on PASS) the packed parameter lane. If parameters pass, it computes
the next-phase local/value budget directly from that native audit. It never
promotes source, starts Stage2/Stage3, or claims self-hosting.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.plan_stage1_codegen_ir_v2_next import (
    DEFAULT_REPORT as DEFAULT_NEXT_PHASE_REPORT,
    build_plan as build_next_phase_plan,
)
from tools.preflight_stage1_codegen_ir_v2_static import (
    DEFAULT_REPORT as DEFAULT_STATIC_PREFLIGHT_REPORT,
    run as run_static_preflight,
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


def _write(path: Path, value: dict[str, object]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_chain(
    *,
    capacity_report_path: Path,
    parameter_report_path: Path,
    next_phase_report_path: Path,
    chain_report_path: Path,
    static_preflight_report_path: Path = DEFAULT_STATIC_PREFLIGHT_REPORT,
) -> dict[str, object]:
    static_preflight = run_static_preflight(report_path=static_preflight_report_path)
    static_pass = static_preflight.get("native_chain_allowed") is True

    capacity: dict[str, object] | None = None
    if static_pass:
        capacity = qualify_capacity(
            report_path=capacity_report_path,
            run_contract_tests=True,
        )
    capacity_pass = bool(
        capacity is not None
        and capacity.get("qualification", {}).get("capacity_candidate")
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
    _write(next_phase_report_path, next_phase)

    if not static_pass:
        chain_status = "BLOCKED_AT_STATIC_PREFLIGHT"
    elif not capacity_pass:
        chain_status = "BLOCKED_AT_CAPACITY_CANDIDATE"
    elif not parameter_pass:
        chain_status = "BLOCKED_AT_PARAMETER_CANDIDATE"
    else:
        chain_status = "PASS_THROUGH_PARAMETER_CANDIDATE"

    result = {
        "schema": "s3.selfhost.codegen-ir-v2-native-chain.v3",
        "canonical_source_mutated": False,
        "static_preflight": {
            "status": "PASS" if static_pass else "FAIL",
            "report": str(static_preflight_report_path.resolve()),
            "storage_reuse": static_preflight.get("storage_reuse_audit", {}).get("status"),
            "array_initializers": static_preflight.get("array_initializer_audit", {}).get("status"),
            "zero_initializer_items": static_preflight.get("array_initializer_audit", {}).get("zero_initializer_items"),
        },
        "capacity_gate": {
            "status": "PASS" if capacity_pass else "FAIL" if capacity is not None else "NOT_RUN",
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
            "report": str(next_phase_report_path.resolve()),
        },
        "chain_status": chain_status,
        "canonical_commit_allowed": False,
        "canonical_commit_reason": "Candidate chain intentionally never mutates/promotes the canonical source. Review native reports first.",
        "general_emitter": "BLOCKED_IR_V2_INCOMPLETE",
        "self_emit": "NOT_STARTED",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }

    _write(chain_report_path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-preflight-report", type=Path, default=DEFAULT_STATIC_PREFLIGHT_REPORT)
    parser.add_argument("--capacity-report", type=Path, default=DEFAULT_CAPACITY_REPORT)
    parser.add_argument("--parameter-report", type=Path, default=DEFAULT_PARAMETER_REPORT)
    parser.add_argument("--next-phase-report", type=Path, default=DEFAULT_NEXT_PHASE_REPORT)
    parser.add_argument("--chain-report", type=Path, default=DEFAULT_CHAIN_REPORT)
    args = parser.parse_args(argv)

    result = run_chain(
        static_preflight_report_path=args.static_preflight_report,
        capacity_report_path=args.capacity_report,
        parameter_report_path=args.parameter_report,
        next_phase_report_path=args.next_phase_report,
        chain_report_path=args.chain_report,
    )
    print(f"CHAIN_REPORT={args.chain_report.resolve()}")
    print(f"STATIC_PREFLIGHT={result['static_preflight']['status']}")
    print(f"STORAGE_REUSE={result['static_preflight']['storage_reuse']}")
    print(f"ARRAY_INITIALIZERS={result['static_preflight']['array_initializers']}")
    print(f"ZERO_INITIALIZER_ITEMS={result['static_preflight']['zero_initializer_items']}")
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
