"""Plan bounded Stage1 capacities exposed by full-source token coverage.

This planner intentionally does not mutate S3 source. It combines the repaired
wide-token-lane model with the discard-compaction semantic model and computes
minimum physical capacities for call metadata, call arguments, structural events
and the current synthetic CFG block pool.

The legacy numeric-record pressure is reported separately from the future IR-v2
semantic value namespace. The planner never treats a lexical numeric-token count
as an SSA/value-namespace requirement and never blindly enlarges semantic value
storage from it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.audit_stage1_compaction_after_token_lane import audit as audit_compaction
from tools.audit_stage1_token_lane_wide_literals import audit as audit_token_lane
from tools.patch_stage1_token_lane_wide_literals import SOURCE


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "full-source-capacity-plan.json"
)
BANK = 365
CURRENT_CALL_CAPACITY = 730
CURRENT_CALL_ARGUMENT_CAPACITY = 746
CURRENT_EVENT_CAPACITY = 1460
CURRENT_BLOCK_CAPACITY = 365
CURRENT_LEGACY_NUMERIC_RECORD_CAPACITY = 1460


def _round_bank(required: int) -> int:
    if required <= 0:
        return BANK
    return ((required + BANK - 1) // BANK) * BANK


def _call_argument_banks(required: int) -> list[int]:
    if required <= 365:
        return [required]
    if required <= 730:
        return [365, required - 365]
    result = [365, 365]
    remaining = required - 730
    while remaining > 0:
        size = min(BANK, remaining)
        result.append(size)
        remaining -= size
    return result


def plan(source: str) -> dict[str, object]:
    token = audit_token_lane(source)
    compaction = audit_compaction(source)
    repaired = token["repaired_candidate_model"]
    call_model = repaired["call_model"]
    matrix = compaction["matrix"]
    cfg = compaction["cfg_reconstruction_model"]
    s0_counts = compaction["token_lane_source"]["counts"]
    s1_counts = compaction["compacted_source"]["counts"]

    calls_required = int(call_model["calls"])
    arguments_required = int(call_model["total_call_arguments"])
    compacted_events_required = int(matrix["E1_S0_events"])
    baseline_events_required = int(matrix["E0_S0_events"])
    blocks_required = int(cfg["S1_required_blocks"])
    numeric_tokens_before = int(s0_counts["numeric_tokens"])
    numeric_tokens_after = int(s1_counts["numeric_tokens"])

    call_selected = max(CURRENT_CALL_CAPACITY, _round_bank(calls_required))
    event_selected = max(CURRENT_EVENT_CAPACITY, _round_bank(compacted_events_required))
    block_selected = max(CURRENT_BLOCK_CAPACITY, _round_bank(blocks_required))
    arg_selected = max(CURRENT_CALL_ARGUMENT_CAPACITY, arguments_required)
    arg_banks = _call_argument_banks(arg_selected)

    routes: list[str] = []
    if calls_required > CURRENT_CALL_CAPACITY:
        routes.append("EXPAND_CALL_METADATA_CAPACITY")
    if arguments_required > CURRENT_CALL_ARGUMENT_CAPACITY:
        routes.append("EXPAND_CALL_ARGUMENT_CAPACITY")
    if compacted_events_required > CURRENT_EVENT_CAPACITY:
        routes.append("EXPAND_OR_FURTHER_COMPACT_EVENT_CAPACITY")
    if blocks_required > CURRENT_BLOCK_CAPACITY:
        routes.append("EXPAND_BLOCK_CAPACITY_FROM_FULL_SOURCE_CFG_MODEL")
    if numeric_tokens_after > CURRENT_LEGACY_NUMERIC_RECORD_CAPACITY:
        routes.append("REMOVE_OR_EXPAND_LEGACY_NUMERIC_RECORD_PRESSURE_BEFORE_IR_V2")
    if not routes:
        routes.append("NATIVE_TOKEN_LANE_THEN_COMPACTION_2X2")

    legacy_numeric_route = (
        "NO_LEGACY_NUMERIC_CAPACITY_CHANGE_REQUIRED"
        if numeric_tokens_after <= CURRENT_LEGACY_NUMERIC_RECORD_CAPACITY
        else "PREFER_ELIMINATE_REDUNDANT_LEGACY_NUMERIC_RECORDING_IF_UNUSED;_OTHERWISE_EXACT_BOUNDED_EXPANSION"
    )

    return {
        "schema": "s3.selfhost.full-source-capacity-plan.v2",
        "status": "STATIC_PLAN_NATIVE_REMEASUREMENT_REQUIRED",
        "native_evidence": False,
        "canonical_source_mutated": False,
        "token_lane_status": token["status"],
        "compaction_static_status": compaction["status"],
        "requirements": {
            "calls": calls_required,
            "call_arguments": arguments_required,
            "events_before_discard_compaction": baseline_events_required,
            "events_after_discard_compaction": compacted_events_required,
            "blocks_after_discard_compaction": blocks_required,
            "legacy_numeric_records_before_compaction": numeric_tokens_before,
            "legacy_numeric_records_after_compaction": numeric_tokens_after,
        },
        "current": {
            "call_capacity": CURRENT_CALL_CAPACITY,
            "call_argument_capacity": CURRENT_CALL_ARGUMENT_CAPACITY,
            "event_capacity": CURRENT_EVENT_CAPACITY,
            "block_capacity": CURRENT_BLOCK_CAPACITY,
            "legacy_numeric_record_capacity": CURRENT_LEGACY_NUMERIC_RECORD_CAPACITY,
        },
        "minimum_physical_plan": {
            "call_capacity_bank_multiple": call_selected,
            "call_banks_365": call_selected // BANK,
            "call_argument_capacity": arg_selected,
            "call_argument_banks": arg_banks,
            "event_capacity_bank_multiple": event_selected,
            "event_banks_365": event_selected // BANK,
            "block_capacity_bank_multiple": block_selected,
            "block_banks_365": block_selected // BANK,
        },
        "routes": routes,
        "legacy_numeric_record_policy": {
            "required_after_compaction": numeric_tokens_after,
            "current_capacity": CURRENT_LEGACY_NUMERIC_RECORD_CAPACITY,
            "route": legacy_numeric_route,
            "semantic_value_namespace_equivalent": False,
            "reason": (
                "ir_value_records currently preserve structural numeric-token records. "
                "They are not the final typed semantic value namespace. If full-source "
                "coverage makes this legacy lane overflow, first prove whether the lane "
                "is read by any required verifier/emitter path before allocating more "
                "storage that IR-v2 intends to replace."
            ),
        },
        "semantic_value_capacity_policy": {
            "auto_expand_from_lexical_numeric_tokens": False,
            "reason": (
                "Typed constant interning, local/parameter identity and instruction-result "
                "def/use must be measured before choosing final semantic value capacity."
            ),
        },
        "qualification_rule": (
            "This is a static minimum planner. Any source-capacity change must be "
            "implemented as a bounded candidate and natively remeasured. Do not "
            "allocate arbitrary oversized pools or treat this report as PASS."
        ),
        "next": routes[0],
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = plan(args.source.resolve().read_text(encoding="utf-8"))
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    requirements = result["requirements"]
    physical = result["minimum_physical_plan"]
    print(f"REPORT={destination}")
    print(f"CALLS_REQUIRED={requirements['calls']}")
    print(f"CALL_ARGUMENTS_REQUIRED={requirements['call_arguments']}")
    print(f"EVENTS_BEFORE_COMPACTION={requirements['events_before_discard_compaction']}")
    print(f"EVENTS_AFTER_COMPACTION={requirements['events_after_discard_compaction']}")
    print(f"BLOCKS_AFTER_COMPACTION={requirements['blocks_after_discard_compaction']}")
    print(f"LEGACY_NUMERIC_RECORDS_AFTER_COMPACTION={requirements['legacy_numeric_records_after_compaction']}")
    print(f"CALL_CAPACITY_PLAN={physical['call_capacity_bank_multiple']}")
    print(f"CALL_ARGUMENT_CAPACITY_PLAN={physical['call_argument_capacity']}")
    print(f"EVENT_CAPACITY_PLAN={physical['event_capacity_bank_multiple']}")
    print(f"BLOCK_CAPACITY_PLAN={physical['block_capacity_bank_multiple']}")
    print(f"NEXT={result['next']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
