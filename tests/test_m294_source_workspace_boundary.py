"""M2.94 source/workspace boundary contracts."""

from pathlib import Path

import pytest

from bootstrap.s3.source_workspace_boundary import (
    SourceUnit,
    SourceWorkspaceBoundaryError,
    WorkspaceLoadRequest,
    run_source_workspace_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (
    ROOT / "selfhost" / "driver" / "source_workspace_boundary_candidate.s3"
).read_text(encoding="utf-8")


def _request(*units: SourceUnit) -> WorkspaceLoadRequest:
    return WorkspaceLoadRequest(tuple(units))


def test_candidate_source_has_one_boundary_entrypoint_and_no_main() -> None:
    assert "fn prepare_workspace_plan" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_units_are_sorted_and_candidate_matches_without_loading_source() -> None:
    request = _request(
        SourceUnit("src/zeta.s3", "f" * 64),
        SourceUnit("src/main.s3", "0" * 64),
    )
    reference, candidate = run_source_workspace_differential(request)
    assert reference == candidate
    assert reference.ordered_paths == ("src/main.s3", "src/zeta.s3")
    assert reference.source_digests == ("0" * 64, "f" * 64)
    assert reference.host_service_required


def test_digest_change_changes_plan_identity() -> None:
    first, _ = run_source_workspace_differential(
        _request(SourceUnit("src/main.s3", "0" * 64))
    )
    second, _ = run_source_workspace_differential(
        _request(SourceUnit("src/main.s3", "1" * 64))
    )
    assert first.plan_identity != second.plan_identity


@pytest.mark.parametrize(
    "path, digest",
    [
        ("src/../main.s3", "0" * 64),
        ("src\\main.s3", "0" * 64),
        ("src/main.s3", "0" * 63 + "G"),
    ],
)
def test_invalid_host_metadata_fails_closed(path: str, digest: str) -> None:
    with pytest.raises(SourceWorkspaceBoundaryError):
        _request(SourceUnit(path, digest))


def test_duplicate_paths_fail_closed() -> None:
    with pytest.raises(SourceWorkspaceBoundaryError, match="unique"):
        _request(
            SourceUnit("src/main.s3", "0" * 64),
            SourceUnit("src/main.s3", "1" * 64),
        )
