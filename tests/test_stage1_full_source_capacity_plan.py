from __future__ import annotations

from tools.patch_stage1_token_lane_wide_literals import SOURCE
from tools.plan_stage1_full_source_capacities import (
    BANK,
    _call_argument_banks,
    _round_bank,
    plan,
)


def test_round_bank_is_minimal_365_multiple() -> None:
    assert _round_bank(1) == BANK
    assert _round_bank(365) == 365
    assert _round_bank(366) == 730
    assert _round_bank(731) == 1095


def test_call_argument_banks_do_not_overallocate_middle_banks() -> None:
    assert _call_argument_banks(16) == [16]
    assert _call_argument_banks(365) == [365]
    assert _call_argument_banks(366) == [365, 1]
    assert _call_argument_banks(746) == [365, 365, 16]
    assert _call_argument_banks(1095) == [365, 365, 365]


def test_real_full_source_plan_is_static_and_fail_closed() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    result = plan(source)

    assert result["status"] == "STATIC_PLAN_NATIVE_REMEASUREMENT_REQUIRED"
    assert result["native_evidence"] is False
    assert result["canonical_source_mutated"] is False
    assert result["requirements"]["calls"] > 0
    assert result["requirements"]["call_arguments"] > 0
    assert result["requirements"]["events_before_discard_compaction"] >= result["requirements"]["events_after_discard_compaction"]
    assert result["minimum_physical_plan"]["call_capacity_bank_multiple"] % 365 == 0
    assert result["minimum_physical_plan"]["event_capacity_bank_multiple"] % 365 == 0
    assert result["value_capacity_policy"]["auto_expand_from_lexical_numeric_tokens"] is False
