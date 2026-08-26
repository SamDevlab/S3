"""Assess readiness to produce the final native Stage1 capacity measurement.

This bridge deliberately cannot emit ``stage1-capacity-measurement.v1``.  It
consumes the pre-IR-v2 chain when available and identifies which lane facts can
be carried forward as provisional full-source requirements, while keeping final
capacity certification blocked until every final IR/storage lane and every
bounded write/overflow proof has native evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRE_IR = (
    ROOT / "reports" / "selfhost" / "stage1" / "pre-ir-v2-token-lane-chain.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "final-capacity-measurement-readiness.json"
)

FINAL_LANES = (
    "tokens",
    "events",
    "blocks",
    "instructions",
    "semantic_values",
    "calls",
    "call_arguments",
    "parameters",
    "locals",
    "storage_objects",
)
PRE_IR_PROVISIONAL_LANES = {
    "events",
    "blocks",
    "calls",
    "call_arguments",
}
FINAL_ONLY_LANES = {
    "instructions",
    "semantic_values",
    "parameters",
    "locals",
    "storage_objects",
}


class MeasurementReadinessError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise MeasurementReadinessError(f"pre-IR chain is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise MeasurementReadinessError(f"pre-IR chain is invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise MeasurementReadinessError("pre-IR chain must be a JSON object")
    if value.get("schema") != "s3.selfhost.pre-ir-v2-token-lane-chain.v2":
        raise MeasurementReadinessError("pre-IR chain schema mismatch")
    return value


def assess(chain: dict[str, Any]) -> dict[str, Any]:
    if chain.get("schema") != "s3.selfhost.pre-ir-v2-token-lane-chain.v2":
        raise MeasurementReadinessError("pre-IR chain schema mismatch")
    native = chain.get("native_token_lane")
    native_pass = bool(
        isinstance(native, dict)
        and native.get("qualification", {}).get("token_lane_candidate")
        == "PASS_NATIVE_CANDIDATE"
    )
    plan = chain.get("full_source_capacity_plan")
    plan_valid = bool(
        isinstance(plan, dict)
        and plan.get("schema") == "s3.selfhost.full-source-capacity-plan.v2"
        and plan.get("status") == "STATIC_PLAN_NATIVE_REMEASUREMENT_REQUIRED"
    )

    provisional: dict[str, Any] = {}
    if plan_valid:
        requirements = plan.get("requirements")
        physical = plan.get("minimum_physical_plan")
        if isinstance(requirements, dict) and isinstance(physical, dict):
            provisional = {
                "calls": {
                    "required_static_full_source": requirements.get("calls"),
                    "planned_capacity": physical.get("call_capacity_bank_multiple"),
                },
                "call_arguments": {
                    "required_static_full_source": requirements.get("call_arguments"),
                    "planned_capacity": physical.get("call_argument_capacity"),
                },
                "events": {
                    "required_static_after_compaction": requirements.get(
                        "events_after_discard_compaction"
                    ),
                    "planned_capacity": physical.get("event_capacity_bank_multiple"),
                },
                "blocks": {
                    "required_static_after_compaction": requirements.get(
                        "blocks_after_discard_compaction"
                    ),
                    "planned_capacity": physical.get("block_capacity_bank_multiple"),
                },
            }

    lane_readiness: dict[str, Any] = {}
    for lane in FINAL_LANES:
        if lane == "tokens":
            status = "NATIVE_PRE_IR_PASS_PROVISIONAL" if native_pass else "BLOCKED_PRE_IR_NATIVE_TOKEN_LANE"
            final_authority = False
        elif lane in PRE_IR_PROVISIONAL_LANES:
            status = (
                "STATIC_FULL_SOURCE_PLAN_AVAILABLE_NATIVE_FINAL_REMEASUREMENT_REQUIRED"
                if plan_valid and native_pass
                else "BLOCKED_PRE_IR_PLAN_OR_NATIVE_TOKEN_LANE"
            )
            final_authority = False
        else:
            status = "WAITING_FOR_FINAL_IR_V2_NATIVE_MEASUREMENT"
            final_authority = False
        lane_readiness[lane] = {
            "status": status,
            "final_capacity_authority": final_authority,
        }

    missing_final_requirements = [
        "exact final Stage1 artifact SHA/bytes",
        "exact final canonical runtime-input SHA/bytes",
        "native final high-water for every bounded lane",
        "complete bounded write-site inventory",
        "out-of-range guard probe PASS for every bounded lane",
        "exhaustive bank dispatch proof for every banked final lane",
        "exhaustive bank roundtrip proof for every banked final lane",
        "native instruction lane requirement/capacity",
        "native typed semantic value namespace requirement/capacity",
        "native parameter lane requirement/capacity",
        "native local lane requirement/capacity",
        "native storage-object lane requirement/capacity",
    ]

    ready = False
    if not native_pass:
        status = "BLOCKED_PRE_IR_NATIVE_TOKEN_LANE"
        next_step = "RUN_OR_REPAIR_PRE_IR_V2_TOKEN_LANE_CHAIN"
    elif not plan_valid:
        status = "BLOCKED_PRE_IR_FULL_SOURCE_CAPACITY_PLAN"
        next_step = "REPAIR_FULL_SOURCE_CAPACITY_PLAN"
    else:
        status = "PASS_PRE_IR_BRIDGE_FINAL_CAPACITY_MEASUREMENT_STILL_BLOCKED"
        next_step = "COMPLETE_IR_V2_THEN_EMIT_FRESH_NATIVE_ALL_LANE_CAPACITY_MEASUREMENT"

    return {
        "schema": "s3.selfhost.stage1-final-capacity-measurement-readiness.v1",
        "status": status,
        "native_pre_ir_token_lane_pass": native_pass,
        "static_full_source_plan_valid": plan_valid,
        "provisional_full_source_capacity_facts": provisional,
        "lane_readiness": lane_readiness,
        "final_only_lanes": sorted(FINAL_ONLY_LANES),
        "missing_final_requirements": missing_final_requirements,
        "can_emit_stage1_capacity_measurement_v1": ready,
        "can_emit_stage1_final_capacity_v1": False,
        "stage2_allowed": False,
        "full_self_hosting": False,
        "rule": "Pre-IR measurements may guide bounded source/storage changes but are never promoted into final capacity evidence. Final measurements must be regenerated on the exact final Stage1 artifact after IR-v2 is complete.",
        "next": next_step,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre-ir", type=Path, default=DEFAULT_PRE_IR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    try:
        result = assess(_load(args.pre_ir.resolve()))
    except MeasurementReadinessError as error:
        parser.exit(2, f"final capacity measurement readiness blocked: {error}\n")
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"NATIVE_PRE_IR_TOKEN_LANE_PASS={result['native_pre_ir_token_lane_pass']}")
    print(f"STATIC_FULL_SOURCE_PLAN_VALID={result['static_full_source_plan_valid']}")
    print("FINAL_CAPACITY_MEASUREMENT_READY=NO")
    print("STAGE2_ALLOWED=NO")
    print(f"NEXT={result['next']}")
    return 0 if str(result["status"]).startswith("PASS_PRE_IR_BRIDGE") else 2


if __name__ == "__main__":
    raise SystemExit(main())
