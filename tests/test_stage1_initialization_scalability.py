from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.audit_stage1_initialization_scalability import (
    audit_source,
    project_state_shape,
)


pytestmark = pytest.mark.s3_fast


def _contract() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    return json.loads(
        (
            root
            / "reports"
            / "selfhost"
            / "stage1"
            / "initialization-analysis-scalability-contract.json"
        ).read_text(encoding="utf-8")
    )


def test_projection_exposes_dense_state_pressure_without_claiming_rss() -> None:
    projection = project_state_shape(21_199, 300)
    assert projection["state_maps_including_initial"] == 601
    assert projection["legacy_dense_state_entries"] == 21_199 * 601
    assert projection["legacy_detailed_report_cell_entries"] == 21_199 * 600
    assert projection["words_per_bitset"] == 332
    assert projection["two_bitset_words_for_same_state_count"] == 332 * 2 * 601
    assert projection["dense_entries_per_bitset_word_projection"] > 30


def test_zero_cell_function_has_zero_state_projection() -> None:
    projection = project_state_shape(0, 10)
    assert projection["state_maps_including_initial"] == 0
    assert projection["legacy_dense_state_entries"] == 0
    assert projection["two_bitset_words_for_same_state_count"] == 0


@pytest.mark.parametrize("cells, blocks", [(-1, 1), (1, -1)])
def test_projection_rejects_negative_dimensions(cells: int, blocks: int) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        project_state_shape(cells, blocks)


def test_small_source_audit_measures_memory_and_reachable_blocks() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut values: i64[4] = [1, 2, 3, 4]\n"
        "    mut index: i64 = 0\n"
        "    while index < 2:\n"
        "        values[index] = values[index] + 1\n"
        "        index = index + 1\n"
        "    return to_tryte(values[0])\n"
    )
    result = audit_source(source, _contract())
    assert result["status"] == "STATIC_STATE_SHAPE_MEASURED"
    assert result["native_evidence"] is False
    assert result["runtime_rss_measurement"] is False
    assert result["totals"]["functions"] == 1
    assert result["totals"]["memory_objects"] >= 1
    assert result["totals"]["memory_cells"] >= 4
    assert result["totals"]["reachable_blocks"] >= 1
    assert result["totals"]["legacy_dense_state_entries"] > 0
    assert result["totals"]["two_bitset_words"] > 0


def test_contract_preserves_validation_when_report_materialization_is_omitted() -> None:
    contract = _contract()
    policy = contract["report_policy"]
    invariants = contract["semantic_invariants"]
    assert policy["report_omission_must_not_skip_analysis"] is True
    assert policy["report_omission_must_not_weaken_diagnostics"] is True
    assert any("unknown-index STORE" in item for item in invariants)
    assert any("verify_ir" in item for item in invariants)
