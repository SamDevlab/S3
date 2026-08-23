"""M2.66 bounded workspace graph candidate contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.workspace_candidate import (
    WorkspaceCandidateError,
    candidate_workspace_fingerprint,
    reference_workspace_fingerprint,
    run_workspace_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/frontend/workspace_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_bounded() -> None:
    assert "fn workspace_graph_fingerprint" in SELFHOST_SOURCE
    assert "tryte[16]" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_candidate_matches_reference_graph() -> None:
    workspace = {"app": ["lib"], "lib": []}
    evidence = run_workspace_differential(workspace)
    assert evidence.reference_fingerprint == reference_workspace_fingerprint(workspace)
    assert evidence.candidate_fingerprint == candidate_workspace_fingerprint(workspace)
    assert evidence.match is True


def test_workspace_order_is_canonical() -> None:
    first = {"app": ["lib", "util"], "lib": [], "util": []}
    second = {"util": [], "app": ["util", "lib"], "lib": []}
    assert reference_workspace_fingerprint(first) == reference_workspace_fingerprint(second)
    assert candidate_workspace_fingerprint(first) == candidate_workspace_fingerprint(second)


def test_candidate_rejects_unknown_import_target() -> None:
    with pytest.raises(WorkspaceCandidateError, match="unknown"):
        candidate_workspace_fingerprint({"app": ["missing"]})


def test_candidate_rejects_empty_workspace() -> None:
    with pytest.raises(WorkspaceCandidateError, match="modules"):
        candidate_workspace_fingerprint({})
