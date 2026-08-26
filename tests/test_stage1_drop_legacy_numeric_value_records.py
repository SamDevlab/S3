from __future__ import annotations

import pytest

from tools.patch_stage1_drop_legacy_numeric_value_records import (
    build_candidate,
    transform_after_token_lane,
)
from tools.patch_stage1_token_lane_wide_literals import SOURCE, transform as repair_token_lane


def test_candidate_keeps_value_banks_but_removes_legacy_writer() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    token_lane = repair_token_lane(canonical)
    candidate = transform_after_token_lane(token_lane)

    assert candidate != token_lane
    assert "return pack_token(position, 2, 0)" in candidate
    assert "ir_value_records_0[value_slot]" not in candidate
    assert "value_bank" not in candidate
    assert "value_slot" not in candidate
    assert "mut ir_value_count: i64 = 0" in candidate
    for bank in range(4):
        assert candidate.count(f"ir_value_records_{bank}") == 1


def test_candidate_is_deterministic() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    assert build_candidate(canonical) == build_candidate(canonical)


def test_removal_requires_token_lane_first() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="requires wide token-lane repair"):
        transform_after_token_lane(canonical)


def test_double_removal_is_rejected() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    token_lane = repair_token_lane(canonical)
    candidate = transform_after_token_lane(token_lane)
    with pytest.raises(ValueError, match="already removed"):
        transform_after_token_lane(candidate)
