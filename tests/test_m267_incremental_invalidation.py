"""M2.67 bounded incremental invalidation candidate contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.invalidation_candidate import (
    InvalidationCandidateError,
    candidate_invalidation_fingerprint,
    reference_invalidation_fingerprint,
    run_invalidation_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/frontend/invalidation_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_bounded() -> None:
    assert "fn incremental_invalidation_fingerprint" in SELFHOST_SOURCE
    assert "fn reaches_changed" in SELFHOST_SOURCE
    assert "tryte[16]" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_changed_dependency_invalidates_transitive_importers() -> None:
    workspace = {"app": ["lib"], "lib": []}
    evidence = run_invalidation_differential(workspace, ["lib"])
    assert evidence.reference_fingerprint == reference_invalidation_fingerprint(
        workspace, ["lib"]
    )
    assert evidence.candidate_fingerprint == candidate_invalidation_fingerprint(
        workspace, ["lib"]
    )
    assert evidence.match is True


def test_changed_leaf_only_invalidates_itself() -> None:
    workspace = {"app": ["lib"], "lib": []}
    assert candidate_invalidation_fingerprint(workspace, ["app"]) == reference_invalidation_fingerprint(
        workspace, ["app"]
    )


def test_transitive_chain_reaches_all_importers() -> None:
    workspace = {"app": ["lib"], "lib": ["core"], "core": []}
    assert candidate_invalidation_fingerprint(workspace, ["core"]) == reference_invalidation_fingerprint(
        workspace, ["core"]
    )


def test_workspace_and_change_order_is_canonical() -> None:
    first = {"app": ["lib", "util"], "lib": ["core"], "util": [], "core": []}
    second = {"core": [], "util": [], "app": ["util", "lib"], "lib": ["core"]}
    assert reference_invalidation_fingerprint(first, ["util", "core"]) == reference_invalidation_fingerprint(
        second, ["core", "util"]
    )
    assert candidate_invalidation_fingerprint(first, ["util", "core"]) == candidate_invalidation_fingerprint(
        second, ["core", "util"]
    )


def test_candidate_rejects_unknown_changed_module() -> None:
    with pytest.raises(InvalidationCandidateError, match="unknown"):
        candidate_invalidation_fingerprint({"app": []}, ["missing"])


def test_candidate_rejects_empty_change_set() -> None:
    with pytest.raises(InvalidationCandidateError, match="non-empty"):
        candidate_invalidation_fingerprint({"app": []}, [])
