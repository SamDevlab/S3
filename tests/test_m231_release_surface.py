from __future__ import annotations

import json

import pytest

from bootstrap.s3.release_surface import (
    PublicSurface,
    ReleaseSurfaceError,
    ReleaseSurfaceInventory,
    SurfaceStability,
    default_release_surface,
    validate_release_surface,
)


def test_release_surface_is_explicit_sorted_and_deterministic() -> None:
    inventory = default_release_surface()
    validate_release_surface(inventory)
    assert json.loads(inventory.json)["format"] == "s3.release-surface.v1"
    assert [item.name for item in inventory.surfaces] == sorted(item.name for item in inventory.surfaces)
    assert inventory.by_stability(SurfaceStability.DEFERRED)
    assert inventory.json == default_release_surface().json


def test_release_surface_rejects_duplicate_or_unclassified_identity() -> None:
    item = PublicSurface("language.syntax", "language", "syntax", "high", SurfaceStability.STABLE_FOR_1_0)
    with pytest.raises(ReleaseSurfaceError, match="sorted and unique"):
        ReleaseSurfaceInventory("1.0-rc", (item, item))
    with pytest.raises(ReleaseSurfaceError, match="stability is invalid"):
        PublicSurface("x", "language", "syntax", "low", "STABLE_FOR_1_0")  # type: ignore[arg-type]


def test_release_surface_requires_explicit_experimental_internal_and_deferred_boundaries() -> None:
    stable = PublicSurface("language.syntax", "language", "syntax", "high", SurfaceStability.STABLE_FOR_1_0)
    inventory = ReleaseSurfaceInventory("1.0-rc", (stable,))
    with pytest.raises(ReleaseSurfaceError, match="stable release surface inventory is incomplete"):
        validate_release_surface(inventory)
