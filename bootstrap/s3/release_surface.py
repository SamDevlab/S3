"""Deterministic public-surface inventory for the S3 1.0 RC boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json


class ReleaseSurfaceError(ValueError):
    """Raised when a release-surface inventory is incomplete or ambiguous."""


class SurfaceStability(str, Enum):
    STABLE_FOR_1_0 = "STABLE_FOR_1_0"
    EXPERIMENTAL = "EXPERIMENTAL"
    INTERNAL = "INTERNAL"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True, slots=True)
class PublicSurface:
    name: str
    category: str
    current_semantics: str
    compatibility_risk: str
    stability: SurfaceStability

    def __post_init__(self) -> None:
        values = (self.name, self.category, self.current_semantics, self.compatibility_risk)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ReleaseSurfaceError("release surface fields must be non-empty strings")
        if not isinstance(self.stability, SurfaceStability):
            raise ReleaseSurfaceError("release surface stability is invalid")

    @property
    def payload(self) -> dict[str, str]:
        return {
            "category": self.category,
            "compatibility_risk": self.compatibility_risk,
            "current_semantics": self.current_semantics,
            "name": self.name,
            "stability": self.stability.value,
        }


@dataclass(frozen=True, slots=True)
class ReleaseSurfaceInventory:
    version: str
    surfaces: tuple[PublicSurface, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ReleaseSurfaceError("release surface version is required")
        names = tuple(surface.name for surface in self.surfaces)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise ReleaseSurfaceError("release surfaces must be sorted and unique")
        if not self.surfaces:
            raise ReleaseSurfaceError("release surface inventory cannot be empty")

    @property
    def payload(self) -> dict[str, object]:
        return {
            "format": "s3.release-surface.v1",
            "surfaces": [surface.payload for surface in self.surfaces],
            "version": self.version,
        }

    @property
    def json(self) -> str:
        return json.dumps(self.payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"

    def by_stability(self, stability: SurfaceStability) -> tuple[PublicSurface, ...]:
        if not isinstance(stability, SurfaceStability):
            raise ReleaseSurfaceError("surface stability is invalid")
        return tuple(surface for surface in self.surfaces if surface.stability is stability)


_REQUIRED_STABLE = frozenset(
    {
        "language.syntax",
        "language.type-and-ownership",
        "module.import-resolution",
        "package.manifest-and-lockfile",
        "diagnostics.codes-and-spans",
        "cli.check-test-build",
        "build.profile-identities",
    }
)


def validate_release_surface(inventory: ReleaseSurfaceInventory) -> None:
    """Require an explicit stable core and explicit non-stable boundaries."""

    if not isinstance(inventory, ReleaseSurfaceInventory):
        raise ReleaseSurfaceError("release surface validation requires an inventory")
    names = {surface.name for surface in inventory.surfaces}
    missing = sorted(_REQUIRED_STABLE - names)
    if missing:
        raise ReleaseSurfaceError(f"stable release surface inventory is incomplete: {missing[0]}")
    if not inventory.by_stability(SurfaceStability.EXPERIMENTAL):
        raise ReleaseSurfaceError("experimental boundaries must be explicit")
    if not inventory.by_stability(SurfaceStability.INTERNAL):
        raise ReleaseSurfaceError("internal boundaries must be explicit")
    if not inventory.by_stability(SurfaceStability.DEFERRED):
        raise ReleaseSurfaceError("environment or capability deferments must be explicit")


def default_release_surface() -> ReleaseSurfaceInventory:
    """Return the checked-in, conservative surface contract for the RC."""

    surfaces = (
        PublicSurface("async.await-ownership", "runtime", "await-crossing values remain explicitly owned", "high", SurfaceStability.STABLE_FOR_1_0),
        PublicSurface("build.profile-identities", "tooling", "development and release profiles bind target and compiler provenance", "medium", SurfaceStability.STABLE_FOR_1_0),
        PublicSurface("cli.check-test-build", "cli", "check, test, build, and hosted run commands expose bounded results", "medium", SurfaceStability.STABLE_FOR_1_0),
        PublicSurface("diagnostics.codes-and-spans", "diagnostics", "diagnostics expose stable codes and source locations", "medium", SurfaceStability.STABLE_FOR_1_0),
        PublicSurface("ffi.explicit-boundary", "ffi", "FFI values cross only explicit bounded handles and buffers", "high", SurfaceStability.STABLE_FOR_1_0),
        PublicSurface("language.syntax", "language", "current parser syntax and literal forms", "high", SurfaceStability.STABLE_FOR_1_0),
        PublicSurface("language.type-and-ownership", "language", "type checking, move semantics, and ownership diagnostics", "critical", SurfaceStability.STABLE_FOR_1_0),
        PublicSurface("lsp.multi-file", "tooling", "multi-file semantic identity and cancellation remain incomplete", "high", SurfaceStability.EXPERIMENTAL),
        PublicSurface("module.import-resolution", "language", "module imports resolve deterministically within a workspace", "high", SurfaceStability.STABLE_FOR_1_0),
        PublicSurface("optimizer.internal-passes", "compiler", "IR and optimizer pass structure is an internal implementation detail", "medium", SurfaceStability.INTERNAL),
        PublicSurface("package.manifest-and-lockfile", "packages", "manifest and lock identities are deterministic and revision-bound", "high", SurfaceStability.STABLE_FOR_1_0),
        PublicSurface("native.aarch64-runtime", "backend", "AArch64 artifact generation is structural unless native evidence exists", "high", SurfaceStability.DEFERRED),
        PublicSurface("native.macos-arm64-runtime", "backend", "macOS ARM64 artifact generation is structural unless macOS evidence exists", "high", SurfaceStability.DEFERRED),
        PublicSurface("http2.dynamic-hpack", "network", "dynamic-table, incremental-indexing, and Huffman paths remain deferred", "high", SurfaceStability.DEFERRED),
    )
    inventory = ReleaseSurfaceInventory("1.0-rc", tuple(sorted(surfaces, key=lambda item: item.name)))
    validate_release_surface(inventory)
    return inventory
