"""M2.75 bounded function declaration and call contracts."""

from pathlib import Path

import pytest

from bootstrap.s3.function_call_candidate import (
    FunctionCallCandidateError,
    candidate_function_call,
    run_function_call_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/semantic/function_call_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_bounded() -> None:
    assert "fn check_function_call" in SELFHOST_SOURCE
    assert "tryte[8]" in SELFHOST_SOURCE
    assert "tryte[64]" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


@pytest.mark.parametrize(
    ("signatures", "query_id", "arguments", "accepted", "result_type", "diagnostic"),
    [
        ([(10, (), 1)], 10, (), True, 1, 0),
        ([(10, (2, 3), 4)], 10, (2, 3), True, 4, 0),
        ([(10, (2, 3), 4)], 10, (2,), False, None, 5),
        ([(10, (2, 3), 4)], 10, (2, 2), False, None, 6),
        ([(10, (), 1)], 99, (), False, None, 4),
        ([(10, (1,), 2), (11, (4,), 3)], 11, (4,), True, 3, 0),
        ([(10, (2,), 1), (11, (3,), 2)], 10, (2,), True, 1, 0),
        ([], 10, (), False, None, 4),
    ],
)
def test_candidate_matches_reference_function_call_rules(
    signatures: list[tuple[int, tuple[int, ...], int]],
    query_id: int,
    arguments: tuple[int, ...],
    accepted: bool,
    result_type: int | None,
    diagnostic: int,
) -> None:
    evidence = run_function_call_differential(signatures, query_id, arguments)
    assert evidence.match is True
    assert evidence.reference.accepted is accepted
    assert evidence.candidate.result_type == result_type
    assert evidence.candidate.diagnostic_code == diagnostic


def test_duplicate_function_ids_fail_closed_in_both_paths() -> None:
    signatures = [(10, (2,), 1), (10, (3,), 2)]
    evidence = run_function_call_differential(signatures, 10, (2,))
    assert evidence.match is True
    assert evidence.candidate.accepted is False
    assert evidence.candidate.diagnostic_code == 2


def test_eight_functions_and_eight_arguments_are_supported() -> None:
    signatures = [
        (index + 1, tuple([2] * 8), 4)
        for index in range(8)
    ]
    evidence = run_function_call_differential(signatures, 8, tuple([2] * 8))
    assert evidence.match is True
    assert evidence.candidate.result_type == 4


def test_bounds_and_input_shapes_fail_closed_before_execution() -> None:
    with pytest.raises(FunctionCallCandidateError, match="function table"):
        candidate_function_call([(index, (), 1) for index in range(9)], 1, ())
    with pytest.raises(FunctionCallCandidateError, match="parameter bound"):
        candidate_function_call([(1, tuple([2] * 9), 1)], 1, ())
    with pytest.raises(TypeError, match="signatures"):
        candidate_function_call("bad", 1, ())  # type: ignore[arg-type]
