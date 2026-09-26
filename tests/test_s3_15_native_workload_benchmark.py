from __future__ import annotations

import pytest

from tools.s3_15_native_workload_benchmark import _paired_ratio_summary


def test_paired_ratio_summary_classifies_material_improvement_deterministically() -> None:
    baseline = [200.0 + index for index in range(21)]
    candidate = [100.0 + index / 2 for index in range(21)]

    first = _paired_ratio_summary(baseline, candidate, seed=1504)
    second = _paired_ratio_summary(baseline, candidate, seed=1504)

    assert first == second
    assert first["classification"] == "MATERIAL_IMPROVEMENT"
    assert first["paired_bootstrap_95_percentile_interval"][0] > 1.05


def test_paired_ratio_summary_rejects_unpaired_or_too_small_samples() -> None:
    with pytest.raises(ValueError, match="equal sample counts >= 3"):
        _paired_ratio_summary([1.0, 2.0], [1.0], seed=1)
    with pytest.raises(ValueError, match="equal sample counts >= 3"):
        _paired_ratio_summary([1.0, 2.0], [1.0, 2.0], seed=1)
