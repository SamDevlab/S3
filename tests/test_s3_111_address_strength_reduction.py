from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from tools.s3_111_address_strength_reduction import (
    SOURCE_PATH,
    SOURCE_SHA256,
    rewrite_point_cloud,
)


def test_address_recurrence_rewrites_exactly_the_two_pinned_loops() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert hashlib.sha256(source.encode()).hexdigest() == SOURCE_SHA256

    candidate = rewrite_point_cloud(source)

    assert candidate.count("mut base: tryte = 0") == 1
    assert candidate.count("                            base = 0\n                            while point < bounded_point_count:") == 1
    assert candidate.count("base = base + 3") == 2
    assert "to_tryte(point * 3)" not in candidate
    assert candidate.count("while point < bounded_point_count:") == 2


def test_address_recurrence_rejects_source_drift() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    with pytest.raises(ValueError, match="source identity mismatch"):
        rewrite_point_cloud(source + "\n")


def test_recurrence_sequence_matches_checked_product_for_full_guarded_domain() -> None:
    tryte_min, tryte_max = -364, 364
    for point_count in range(1, 122):
        base = 0
        candidate_indices = []
        for _point in range(point_count):
            candidate_indices.append(base)
            base += 3
            assert tryte_min <= base <= tryte_max
        assert candidate_indices == [point * 3 for point in range(point_count)]
        assert base == point_count * 3


def test_address_recurrence_candidate_compiles_under_o1() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    compilation = compile_source(rewrite_point_cloud(source), OptimizationLevel.O1)
    _ir, assembly = compilation.require_ordinary_artifacts()
    assert any(function.name == "point_cloud_summary" for function in assembly.functions)
