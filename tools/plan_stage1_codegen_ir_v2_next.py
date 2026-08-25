"""Plan the next Stage1 codegen-IR-v2 phase from native parameter evidence.

This tool never mutates the canonical compiler.  It consumes the parameter
candidate report when available and computes bounded headroom plus deterministic
parameter/local value-ID reservations.  Without native parameter evidence it
returns WAITING_FOR_NATIVE_PARAMETER_REPORT rather than substituting static
projections for execution evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARAMETER_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-parameters-native-candidate.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-next-phase-budget.json"
)

EVENT_CAPACITY = 1460
VALUE_CAPACITY = 1460
BLOCK_CAPACITY = 365
CALL_CAPACITY = 730
CALL_ARGUMENT_CAPACITY = 746
LOCAL_RECORD_CAPACITY = 64


class PlanError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PlanError(f"cannot read native parameter report: {error}") from error
    if not isinstance(value, dict):
        raise PlanError("native parameter report must be a JSON object")
    return value


def _int(audit: dict[str, Any], key: str) -> int:
    value = audit.get(key)
    if not isinstance(value, int) or value < 0:
        raise PlanError(f"missing or invalid native audit field: {key}")
    return value


def build_plan(parameter_report: dict[str, Any] | None) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema": "s3.selfhost.codegen-ir-v2-next-phase-budget.v1",
        "canonical_source_mutated": False,
        "native_evidence": parameter_report is not None,
        "capacities": {
            "events": EVENT_CAPACITY,
            "values": VALUE_CAPACITY,
            "blocks": BLOCK_CAPACITY,
            "calls": CALL_CAPACITY,
            "call_arguments": CALL_ARGUMENT_CAPACITY,
            "local_records": LOCAL_RECORD_CAPACITY,
        },
        "local_record_strategy": "ONE_PACKED_I64_64_LANE",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }
    if parameter_report is None:
        base.update({
            "status": "WAITING_FOR_NATIVE_PARAMETER_REPORT",
            "local_ir_v2_start_allowed": False,
            "reason": "Post-parameter native counts are required before selecting the next bounded source transform.",
        })
        return base

    if parameter_report.get("schema") != "s3.selfhost.codegen-ir-v2-parameters-native-candidate.v1":
        raise PlanError("unexpected parameter report schema")
    qualification = parameter_report.get("qualification") or {}
    if qualification.get("parameter_ir_v2_candidate") != "PASS_NATIVE_CANDIDATE":
        raise PlanError("parameter IR-v2 candidate is not a native PASS candidate")
    if parameter_report.get("canonical_source_mutated") is not False:
        raise PlanError("parameter candidate report must come from non-mutating qualification")

    self_source = parameter_report.get("self_source") or {}
    audit = self_source.get("audit")
    if not isinstance(audit, dict):
        raise PlanError("parameter report does not contain a native self-source audit")

    parameters = _int(audit, "parameter_count")
    locals_count = _int(audit, "local_count")
    events = _int(audit, "ir_instruction_count")
    values = _int(audit, "ir_value_count")
    blocks = _int(audit, "ir_block_count")
    calls = _int(audit, "ast_call_count")

    parameter_first = 0
    parameter_end = parameters
    local_first = parameter_end
    local_end = local_first + locals_count
    first_dynamic = local_end

    guards = {
        "parameter_count_fits_reserved_domain": parameters <= LOCAL_RECORD_CAPACITY,
        "local_count_fits_packed_lane": locals_count <= LOCAL_RECORD_CAPACITY,
        "storage_value_reservation_fits_value_pool": local_end < VALUE_CAPACITY,
        "event_headroom_positive": events < EVENT_CAPACITY,
        "value_headroom_positive": values < VALUE_CAPACITY,
        "block_headroom_positive": blocks < BLOCK_CAPACITY,
        "call_headroom_positive": calls < CALL_CAPACITY,
    }

    base.update({
        "status": "READY_FOR_LOCAL_IR_V2_DESIGN" if all(guards.values()) else "BLOCKED_BY_NATIVE_CAPACITY",
        "native_parameter_audit": audit,
        "headroom": {
            "events": EVENT_CAPACITY - events,
            "values": VALUE_CAPACITY - values,
            "blocks": BLOCK_CAPACITY - blocks,
            "calls": CALL_CAPACITY - calls,
            "local_records": LOCAL_RECORD_CAPACITY - locals_count,
        },
        "value_id_reservations": {
            "parameters": {"start": parameter_first, "end_exclusive": parameter_end},
            "local_storage": {"start": local_first, "end_exclusive": local_end},
            "first_instruction_constant_or_result_id": first_dynamic,
            "collision_free": parameter_end <= local_first and local_end <= VALUE_CAPACITY,
        },
        "guards": guards,
        "local_ir_v2_start_allowed": all(guards.values()),
        "next": (
            "LOCAL_IDENTITY_TYPE_MUTABILITY_FRAME_SLOT_CANDIDATE"
            if all(guards.values())
            else "CAPACITY_REDESIGN_BEFORE_LOCAL_IR_V2"
        ),
    })
    return base


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameter-report", type=Path, default=DEFAULT_PARAMETER_REPORT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="write a WAITING plan instead of failing when native evidence is absent",
    )
    args = parser.parse_args(argv)

    parameter_report: dict[str, Any] | None
    if args.parameter_report.exists():
        parameter_report = _load(args.parameter_report.resolve())
    elif args.allow_missing:
        parameter_report = None
    else:
        parser.error("native parameter report does not exist; run the native candidate chain first")

    try:
        report = build_plan(parameter_report)
    except PlanError as error:
        parser.exit(2, f"next-phase planning blocked: {error}\n")

    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"REPORT={destination}")
    print(f"STATUS={report['status']}")
    print(f"LOCAL_IR_V2_START_ALLOWED={report['local_ir_v2_start_allowed']}")
    if "headroom" in report:
        print(f"EVENT_HEADROOM={report['headroom']['events']}")
        print(f"VALUE_HEADROOM={report['headroom']['values']}")
        print(f"BLOCK_HEADROOM={report['headroom']['blocks']}")
        print(f"LOCAL_RECORD_HEADROOM={report['headroom']['local_records']}")
        print(f"FIRST_DYNAMIC_VALUE_ID={report['value_id_reservations']['first_instruction_constant_or_result_id']}")
    print("CANONICAL_SOURCE_MUTATED=False")
    return 0 if report["local_ir_v2_start_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
