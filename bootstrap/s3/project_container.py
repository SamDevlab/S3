"""Deterministic project-container model for M1.37."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


class ProjectContainerError(ValueError):
    """Raised when a project container violates its structural contract."""


_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


@dataclass(frozen=True, slots=True)
class ProjectUnit:
    name: str
    sources: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _NAME.fullmatch(self.name):
            raise ProjectContainerError(f"invalid project unit name {self.name!r}")
        if not self.sources or any(not source for source in self.sources):
            raise ProjectContainerError("project unit must contain source names")
        if tuple(sorted(set(self.sources))) != self.sources:
            raise ProjectContainerError("project unit sources must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ProjectContainer:
    root: str
    units: tuple[ProjectUnit, ...]

    def __post_init__(self) -> None:
        if not self.root or not _NAME.fullmatch(self.root):
            raise ProjectContainerError(f"invalid project root {self.root!r}")
        names = tuple(unit.name for unit in self.units)
        if names != tuple(sorted(names)):
            raise ProjectContainerError("project units must be sorted by name")
        if len(set(names)) != len(names):
            raise ProjectContainerError("project unit names must be unique")

    @property
    def manifest(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return tuple((unit.name, unit.sources) for unit in self.units)

    @property
    def manifest_sha256(self) -> str:
        payload = repr((self.root, self.manifest)).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
