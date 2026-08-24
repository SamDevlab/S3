"""M2.73 bounded scalar type-checking contracts."""

from pathlib import Path

import pytest

from bootstrap.s3.scalar_type_checking_candidate import (
    ScalarTypeCheckingError,
    candidate_scalar_type_check,
    reference_scalar_type_check,
    run_scalar_type_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/semantic/scalar_type_checking_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_scalar_bounded() -> None:
    assert "fn check_scalar_type" in SELFHOST_SOURCE
    assert "tryte" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


@pytest.mark.parametrize(
    ("operation", "left", "right", "target", "accepted", "result_type"),
    [
        ("assign", 1, 0, 1, True, 1),
        ("assign", 3, 0, 4, False, None),
        ("add", 2, 2, 0, True, 2),
        ("multiply", 3, 3, 0, True, 3),
        ("minimum", 2, 2, 0, True, 2),
        ("minimum", 3, 3, 0, False, None),
        ("equal", 4, 4, 0, True, 1),
        ("less", 2, 3, 0, False, None),
        ("to_i64", 2, 0, 0, True, 3),
        ("to_f64", 3, 0, 0, True, 4),
        ("to_tryte", 3, 0, 0, True, 2),
        ("to_tryte", 4, 0, 0, False, None),
    ],
)
def test_candidate_matches_reference_scalar_rules(
    operation: str,
    left: int,
    right: int,
    target: int,
    accepted: bool,
    result_type: int | None,
) -> None:
    evidence = run_scalar_type_differential(operation, left, right, target)
    assert evidence.match is True
    assert evidence.reference.accepted is accepted
    assert evidence.candidate.result_type == result_type


def test_comparison_result_is_trit_for_each_scalar_domain() -> None:
    for type_id in (1, 2, 3, 4):
        result = candidate_scalar_type_check("compare", type_id, type_id)
        assert result.accepted is True
        assert result.result_type == 1


def test_mismatched_arithmetic_and_unknown_type_fail_closed() -> None:
    result = candidate_scalar_type_check("add", 2, 3)
    assert result.accepted is False
    assert result.diagnostic_code == 4
    with pytest.raises(ScalarTypeCheckingError, match="scalar type range"):
        candidate_scalar_type_check("add", 5, 5)


def test_unsupported_operation_is_rejected_before_execution() -> None:
    with pytest.raises(ScalarTypeCheckingError, match="unsupported"):
        reference_scalar_type_check("bitwise", 2, 2)
