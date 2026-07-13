"""Internal target identities for S3 native generation routes."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass


_TARGET_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class UnknownTargetError(ValueError):
    """Raised when an internal target lookup names no supported target."""


@dataclass(frozen=True, slots=True)
class TargetSpec:
    name: str
    architecture: str
    environment: str

    def __post_init__(self) -> None:
        for field_name in ("name", "architecture", "environment"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"target {field_name} must be a non-empty string")
        if _TARGET_NAME.fullmatch(self.name) is None:
            raise ValueError(f"invalid canonical target name {self.name!r}")


@dataclass(frozen=True, slots=True)
class TargetCatalog:
    _targets: tuple[TargetSpec, ...]

    def __init__(self, targets: Iterable[TargetSpec]) -> None:
        items = tuple(targets)
        names: set[str] = set()
        duplicates: set[str] = set()
        for target in items:
            if not isinstance(target, TargetSpec):
                raise TypeError("target catalog entries must be TargetSpec values")
            if target.name in names:
                duplicates.add(target.name)
            names.add(target.name)
        if duplicates:
            rendered = ", ".join(sorted(duplicates))
            raise ValueError(f"duplicate target(s): {rendered}")
        object.__setattr__(
            self,
            "_targets",
            tuple(sorted(items, key=lambda target: target.name)),
        )

    @property
    def targets(self) -> tuple[TargetSpec, ...]:
        return self._targets

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(target.name for target in self._targets)

    def get(self, name: str) -> TargetSpec:
        for target in self._targets:
            if target.name == name:
                return target
        raise UnknownTargetError(f"unknown target {name!r}")

    def __iter__(self) -> Iterator[TargetSpec]:
        return iter(self._targets)


LINUX_X86_64_TARGET = TargetSpec(
    name="linux-x86_64",
    architecture="x86_64",
    environment="linux",
)

BUILTIN_TARGETS = (LINUX_X86_64_TARGET,)


def builtin_target_catalog() -> TargetCatalog:
    return TargetCatalog(BUILTIN_TARGETS)
