"""M2.77 bounded block termination and return-path contracts."""

from pathlib import Path

import pytest

from bootstrap.s3.control_flow_candidate import (
    ControlFlowCandidateError,
    M277_BRANCH,
    M277_INFINITE_LOOP,
    M277_NORMAL,
    M277_RETURN,
    M277_TERMINATE,
    candidate_control_flow,
    run_control_flow_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/semantic/control_flow_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_bounded() -> None:
    assert "fn check_control_flow" in SELFHOST_SOURCE
    assert "tryte[8]" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


@pytest.mark.parametrize(
    ("statements", "requires_return", "accepted", "classification", "diagnostic"),
    [
        ([], False, True, "fallthrough", 0),
        ([(M277_RETURN, 0, 0)], True, True, "returns", 0),
        ([(M277_NORMAL, 0, 0), (M277_RETURN, 0, 0)], True, True, "returns", 0),
        ([(M277_TERMINATE, 0, 0)], False, True, "terminates", 0),
        ([(M277_BRANCH, 1, 1)], True, True, "returns", 0),
        ([(M277_BRANCH, 1, 2)], False, True, "terminates", 0),
        ([(M277_INFINITE_LOOP, 0, 0)], False, True, "terminates", 0),
        ([(M277_BRANCH, 1, 0)], True, False, None, 1),
        ([(M277_RETURN, 0, 0), (M277_NORMAL, 0, 0)], False, False, None, 2),
    ],
)
def test_candidate_matches_reference_flow_rules(
    statements: list[tuple[int, int, int]],
    requires_return: bool,
    accepted: bool,
    classification: str | None,
    diagnostic: int,
) -> None:
    reference, candidate = run_control_flow_differential(
        statements, requires_return=requires_return
    )
    assert reference == candidate
    assert candidate.accepted is accepted
    assert candidate.classification == classification
    assert candidate.diagnostic_code == diagnostic


def test_bounds_and_invalid_branch_metadata_fail_closed_before_execution() -> None:
    with pytest.raises(ControlFlowCandidateError, match="statement bound"):
        candidate_control_flow([(M277_NORMAL, 0, 0)] * 9, requires_return=False)
    with pytest.raises(ControlFlowCandidateError, match="branch_left"):
        candidate_control_flow([(M277_BRANCH, 3, 1)], requires_return=False)
    with pytest.raises(TypeError, match="requires_return"):
        candidate_control_flow([], requires_return=1)  # type: ignore[arg-type]
