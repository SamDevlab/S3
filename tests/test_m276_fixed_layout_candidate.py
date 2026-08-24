"""M2.76 bounded record, enum and fixed-layout identity contracts."""

from pathlib import Path

import pytest

from bootstrap.s3.fixed_layout_candidate import (
    FixedLayoutCandidateError,
    enum_layout_candidate,
    record_layout_candidate,
    run_fixed_layout_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/semantic/fixed_layout_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_bounded() -> None:
    assert "fn record_layout_summary" in SELFHOST_SOURCE
    assert "fn enum_layout_summary" in SELFHOST_SOURCE
    assert "tryte[8]" in SELFHOST_SOURCE
    assert "tryte[64]" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


@pytest.mark.parametrize(
    ("fields", "variants", "record_cells", "enum_cells"),
    [
        ((), ((),), 0, 1),
        ((1,), ((2,), ()), 1, 2),
        ((2, 3, 4), ((1, 2), (4, 3, 2)), 3, 4),
        (tuple([4] * 8), tuple(tuple([1] * 8) for _ in range(8)), 8, 9),
    ],
)
def test_candidate_matches_reference_fixed_layout_rules(
    fields: tuple[int, ...],
    variants: tuple[tuple[int, ...], ...],
    record_cells: int,
    enum_cells: int,
) -> None:
    record_reference, record_candidate, enum_reference, enum_candidate = (
        run_fixed_layout_differential(fields, variants)
    )
    assert record_reference == record_candidate
    assert enum_reference == enum_candidate
    assert record_candidate.cell_count == record_cells
    assert enum_candidate.cell_count == enum_cells


def test_record_identity_is_deterministic_and_content_sensitive() -> None:
    first = record_layout_candidate((1, 2, 3))
    second = record_layout_candidate((1, 2, 3))
    changed = record_layout_candidate((1, 2, 4))
    assert first == second
    assert first.identity != changed.identity


def test_enum_identity_preserves_variant_order_and_payload_shape() -> None:
    first = enum_layout_candidate(((1,), (2, 3)))
    reordered = enum_layout_candidate(((2, 3), (1,)))
    changed = enum_layout_candidate(((1,), (2, 4)))
    assert first.identity != reordered.identity
    assert first.identity != changed.identity
    assert first.cell_count == reordered.cell_count == 3


def test_invalid_record_and_enum_bounds_fail_closed_before_execution() -> None:
    with pytest.raises(FixedLayoutCandidateError, match="field bound"):
        record_layout_candidate(tuple([1] * 9))
    with pytest.raises(FixedLayoutCandidateError, match="variant bound"):
        enum_layout_candidate(tuple(() for _ in range(9)))
    with pytest.raises(FixedLayoutCandidateError, match="scalar type"):
        record_layout_candidate((5,))
    with pytest.raises(TypeError, match="variants"):
        enum_layout_candidate("bad")  # type: ignore[arg-type]
