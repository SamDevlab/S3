"""Plan the next Stage1 codegen-IR-v2 phase from native parameter evidence.

This tool never mutates the canonical compiler. It consumes a native parameter
candidate report and computes bounded headroom plus the *planned* symbol/value
ID domains for the local-metadata and later unified-value phases.

Important: the current ``ir_value_records`` stream is a legacy structural
numeric-token stream, not the final semantic def/use namespace. Parameter/local
value IDs therefore remain logical reservations until a separately qualified
namespace rebuild migrates/replaces the legacy value stream. The planner must
never label those overlapping domains collision-free.
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
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise PlanError(f"missing or invalid native audit field: {key}")
    return value


def build_plan(parameter_report: dict[str, Any] | None) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema": "s3.selfhost.codegen-ir-v2-next-phase-budget.v2",
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
            "unified_value_namespace_start_allowed": False,
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

    # These IDs are planned semantic IDs. They do NOT yet coexist safely with
    # the legacy structural numeric-token value stream, which currently also
    # occupies [0, values). A later qualified rebuild must migrate/rewrite it.
    legacy_value_start = 0
    legacy_value_end = values
    symbol_overlap = max(
        0,
        min(local_end, legacy_value_end) - max(parameter_first, legacy_value_start),
    )
    conservative_combined_required = values + local_end
    conservative_combined_fits = conservative_combined_required <= VALUE_CAPACITY

    guards = {
        "parameter_count_fits_reserved_domain": parameters <= LOCAL_RECORD_CAPACITY,
        "local_count_fits_packed_lane": locals_count <= LOCAL_RECORD_CAPACITY,
        "planned_symbol_id_domain_fits_value_pool": local_end <= VALUE_CAPACITY,
        "event_headroom_positive": events < EVENT_CAPACITY,
        "legacy_value_headroom_positive": values < VALUE_CAPACITY,
        "block_headroom_positive": blocks < BLOCK_CAPACITY,
        "call_headroom_positive": calls < CALL_CAPACITY,
    }
    local_start_allowed = all(guards.values())

    namespace_transition = {
        "legacy_structural_value_stream": {
            "start": legacy_value_start,
            "end_exclusive": legacy_value_end,
            "count": values,
            "status": "LEGACY_NUMERIC_TOKEN_STREAM_NOT_FINAL_DEF_USE_NAMESPACE",
        },
        "planned_symbol_value_domain": {
            "start": parameter_first,
            "end_exclusive": local_end,
            "count": local_end,
        },
        "overlap_count": symbol_overlap,
        "legacy_and_planned_domains_currently_overlap": symbol_overlap > 0,
        "migration_required": symbol_overlap > 0,
        "allowed_migration": (
            "REBUILD_OR_REBASE_LEGACY_VALUE_RECORDS_UNDER_SEPARATELY_QUALIFIED_TRANSFORM"
        ),
        "forbidden_interpretation": (
            "DO_NOT_TREAT_PARAMETER_OR_LOCAL_VALUE_IDS_AS_ALREADY_COLLISION_FREE_WITH_LEGACY_IR_VALUE_RECORDS"
        ),
        "conservative_no_compaction_required_slots": conservative_combined_required,
        "conservative_no_compaction_fits_value_capacity": conservative_combined_fits,
        "value_compaction_required_before_unified_rebuild": not conservative_combined_fits,
        "aggregate_zero_init_may_reduce_required_slots": True,
        "static_zero_counts_are_not_native_headroom": True,
    }

    base.update({
        "status": "READY_FOR_LOCAL_IR_V2_DESIGN" if local_start_allowed else "BLOCKED_BY_NATIVE_CAPACITY",
        "native_parameter_audit": audit,
        "headroom": {
            "events": EVENT_CAPACITY - events,
            "legacy_values": VALUE_CAPACITY - values,
            "blocks": BLOCK_CAPACITY - blocks,
            "calls": CALL_CAPACITY - calls,
            "local_records": LOCAL_RECORD_CAPACITY - locals_count,
            "conservative_values_after_symbol_reservation": (
                VALUE_CAPACITY - conservative_combined_required
            ),
        },
        "value_id_reservations": {
            "status": "LOGICAL_RESERVATION_PENDING_NAMESPACE_REBUILD",
            "parameters": {"start": parameter_first, "end_exclusive": parameter_end},
            "local_storage": {"start": local_first, "end_exclusive": local_end},
            "first_instruction_constant_or_result_id": first_dynamic,
            "parameter_and_local_ranges_nonoverlapping": parameter_end <= local_first,
            "planned_symbol_domain_fits": local_end <= VALUE_CAPACITY,
            "collision_free_with_legacy_value_stream": symbol_overlap == 0,
        },
        "namespace_transition": namespace_transition,
        "guards": guards,
        "local_ir_v2_start_allowed": local_start_allowed,
        # This stays false even if the conservative combined count fits: a
        # concrete transform/verifier has not yet rebuilt the namespace.
        "unified_value_namespace_start_allowed": False,
        "next": (
            "LOCAL_IDENTITY_TYPE_MUTABILITY_FRAME_SLOT_CANDIDATE"
            if local_start_allowed
            else "CAPACITY_REDESIGN_BEFORE_LOCAL_IR_V2"
        ),
        "after_local_candidate": (
            "QUALIFY_VALUE_NAMESPACE_REBUILD_WITH_EXPLICIT_LEGACY_MIGRATION"
            if local_start_allowed
            else "NOT_APPLICABLE"
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
    print(f"UNIFIED_VALUE_NAMESPACE_START_ALLOWED={report['unified_value_namespace_start_allowed']}")
    if "headroom" in report:
        print(f"EVENT_HEADROOM={report['headroom']['events']}")
        print(f"LEGACY_VALUE_HEADROOM={report['headroom']['legacy_values']}")
        print(f"BLOCK_HEADROOM={report['headroom']['blocks']}")
        print(f"LOCAL_RECORD_HEADROOM={report['headroom']['local_records']}")
        print(f"FIRST_DYNAMIC_VALUE_ID={report['value_id_reservations']['first_instruction_constant_or_result_id']}")
        print(f"LEGACY_VALUE_ID_OVERLAP={report['namespace_transition']['overlap_count']}")
        print(f"VALUE_NAMESPACE_MIGRATION_REQUIRED={report['namespace_transition']['migration_required']}")
        print(f"CONSERVATIVE_COMBINED_VALUE_SLOTS={report['namespace_transition']['conservative_no_compaction_required_slots']}")
    print("CANONICAL_SOURCE_MUTATED=False")
    return 0 if report["local_ir_v2_start_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
