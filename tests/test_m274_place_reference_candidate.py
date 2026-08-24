"""M2.74 bounded place and reference semantic contracts."""

from pathlib import Path

import pytest

from bootstrap.s3.place_reference_candidate import (
    M274_MUTABLE_REF,
    M274_SHARED_REF,
    M274_VALUE,
    PlaceReferenceCandidateError,
    candidate_place_operation,
    run_place_reference_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/semantic/place_reference_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_bounded() -> None:
    assert "fn check_place_operation" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE
    assert "tryte" in SELFHOST_SOURCE


@pytest.mark.parametrize(
    ("operation", "kind", "readable", "writable", "addressable", "initialized", "accepted", "result_kind"),
    [
        ("read", M274_VALUE, True, False, True, True, True, M274_VALUE),
        ("read", M274_VALUE, True, False, True, False, False, None),
        ("write", M274_VALUE, True, True, True, True, True, M274_VALUE),
        ("write", M274_VALUE, True, False, True, True, False, None),
        ("address_shared", M274_VALUE, True, False, True, True, True, M274_SHARED_REF),
        ("address_mutable", M274_VALUE, True, True, True, True, True, M274_MUTABLE_REF),
        ("address_mutable", M274_VALUE, True, False, True, True, False, None),
        ("deref_shared", M274_SHARED_REF, True, False, False, True, True, M274_VALUE),
        ("deref_shared", M274_VALUE, True, False, True, True, False, None),
        ("deref_mutable", M274_MUTABLE_REF, True, True, False, True, True, M274_VALUE),
        ("deref_mutable", M274_SHARED_REF, True, False, False, True, False, None),
        ("reborrow_shared", M274_MUTABLE_REF, True, True, False, True, True, M274_SHARED_REF),
        ("reborrow_mutable", M274_MUTABLE_REF, True, True, False, True, True, M274_MUTABLE_REF),
        ("reborrow_mutable", M274_SHARED_REF, True, False, False, True, False, None),
    ],
)
def test_candidate_matches_reference_place_rules(
    operation: str,
    kind: int,
    readable: bool,
    writable: bool,
    addressable: bool,
    initialized: bool,
    accepted: bool,
    result_kind: int | None,
) -> None:
    evidence = run_place_reference_differential(
        operation, 3, kind, readable, writable, addressable, initialized
    )
    assert evidence.match is True
    assert evidence.reference.accepted is accepted
    assert evidence.candidate.result_place_kind == result_kind


def test_invalid_place_requests_fail_closed_before_execution() -> None:
    with pytest.raises(PlaceReferenceCandidateError, match="unsupported"):
        candidate_place_operation("borrow_mut", 3, M274_VALUE, True, True, True, True)
    with pytest.raises(PlaceReferenceCandidateError, match="type_id"):
        candidate_place_operation("read", 5, M274_VALUE, True, False, True, True)
    with pytest.raises(TypeError, match="readable"):
        candidate_place_operation("read", 3, M274_VALUE, 1, False, True, True)  # type: ignore[arg-type]
