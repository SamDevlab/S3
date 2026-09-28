from __future__ import annotations

import pytest

from tools.s3_111_hot_fallthrough_timing import paired_summary


def test_paired_summary_detects_stable_improvement() -> None:
    result = paired_summary([20.0] * 21, [10.0] * 21)

    assert result["classification"] == "MATERIAL_IMPROVEMENT"
    assert result["baseline_over_candidate_median_ratio"] == 2.0


def test_paired_summary_detects_no_material_change() -> None:
    result = paired_summary([10.0] * 21, [10.0] * 21)

    assert result["classification"] == "NO_MATERIAL_CHANGE_WITHIN_5_PERCENT"


def test_paired_summary_rejects_unpaired_samples() -> None:
    with pytest.raises(ValueError, match="equal sample counts"):
        paired_summary([1.0, 2.0, 3.0], [1.0, 2.0])


def test_paired_summary_rejects_too_few_pairs() -> None:
    with pytest.raises(ValueError, match="equal sample counts"):
        paired_summary([1.0, 2.0], [1.0, 2.0])
