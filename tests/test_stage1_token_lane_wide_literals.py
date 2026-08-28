from __future__ import annotations

import pytest

from tools.audit_stage1_token_lane_wide_literals import (
    _execute,
    _token_positions,
)
from tools.patch_stage1_token_lane_wide_literals import (
    LEGACY_NUMERIC_PACK,
    SAFE_NUMERIC_PACK,
    SOURCE,
    is_applied,
    transform,
)


def test_transform_is_deterministic_and_does_not_add_functions_or_locals() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    already_applied = is_applied(source)
    first = source if already_applied else transform(source)
    second = source if already_applied else transform(source)

    assert first == second
    if already_applied:
        assert first == source
    else:
        assert first != source
    assert first.count("fn ") == source.count("fn ")
    assert first.count("mut ") == source.count("mut ")
    assert LEGACY_NUMERIC_PACK not in first
    assert first.count(SAFE_NUMERIC_PACK) == 1
    assert first.count("mut slot: i64 = actual_start") == 1
    assert first.count("slot = token_count / 16") == 1
    assert first.count("slot = token_count - slot * 16") == 1
    assert first.count("mut function_statements: i64[64]") == 1
    assert "to_i64(function_statements[ir_index])" not in first
    assert first.count("ir_value[ir_index] = function_statements[ir_index]") == 2


def test_transform_rejects_second_application() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    candidate = source if is_applied(source) else transform(source)
    with pytest.raises(ValueError, match="already applied"):
        transform(candidate)


def test_legacy_lane_corrupts_wide_numeric_cursor() -> None:
    source = "mut value: i64 = 1000000000000\n"
    legacy = _execute(source, recover_numeric=False)

    assert legacy["full_character_coverage"] is False
    assert legacy["numeric_lane_spill_count"] == 1
    spill = legacy["terminating_spill"]
    assert isinstance(spill, dict)
    assert spill["value"] == 1_000_000_000_000
    assert spill["decoded_next"] > len(source)


def test_recovered_lane_preserves_wide_signed_numeric_tokens() -> None:
    source = "mut a: i64 = 1000000000000\nmut b: i64 = -1000000000000\n"
    repaired = _execute(source, recover_numeric=True)

    assert repaired["full_character_coverage"] is True
    assert repaired["terminating_spill"] is None
    execution = repaired["execution"]
    values = [
        token.value
        for token, _ in execution
        if token.kind == 2
    ]
    assert 1_000_000_000_000 in values
    assert -1_000_000_000_000 in values


def test_recovered_lane_covers_all_canonical_lexical_tokens() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    repaired = _execute(source, recover_numeric=True)
    positioned = _token_positions(source)

    assert repaired["full_character_coverage"] is True
    assert repaired["terminating_spill"] is None
    assert repaired["executed_token_count"] == len(positioned)
    assert repaired["numeric_lane_spill_count"] > 0


def test_candidate_recovered_lane_covers_all_candidate_tokens() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    candidate = source if is_applied(source) else transform(source)
    repaired = _execute(candidate, recover_numeric=True)

    assert repaired["full_character_coverage"] is True
    assert repaired["terminating_spill"] is None
    assert repaired["executed_token_count"] == repaired["lexical_token_count"]
