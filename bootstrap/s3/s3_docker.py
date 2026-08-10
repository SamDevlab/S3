"""Deterministic Docker execution contract for M1.38."""

from __future__ import annotations

import re
from dataclasses import dataclass


class DockerConfigError(ValueError):
    """Raised when a Docker configuration violates the S3 contract."""


_IMAGE = re.compile(r"^[a-z0-9](?:[a-z0-9._/-]*[a-z0-9])?(?::[A-Za-z0-9][A-Za-z0-9_.-]*)?$")
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class DockerSpec:
    image: str
    command: tuple[str, ...]
    environment: tuple[tuple[str, str], ...] = ()
    timeout_seconds: int = 60

    def __post_init__(self) -> None:
        if not _IMAGE.fullmatch(self.image):
            raise DockerConfigError(f"invalid Docker image {self.image!r}")
        if not self.command or any(not item for item in self.command):
            raise DockerConfigError("Docker command must be non-empty")
        names = tuple(name for name, _ in self.environment)
        if any(not _ENV_NAME.fullmatch(name) for name in names):
            raise DockerConfigError("invalid environment variable name")
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise DockerConfigError("environment must be sorted and unique")
        if not isinstance(self.timeout_seconds, int) or not 1 <= self.timeout_seconds <= 3600:
            raise DockerConfigError("Docker timeout must be between 1 and 3600 seconds")

    @property
    def argv(self) -> tuple[str, ...]:
        return ("docker", "run", "--rm", self.image, *self.command)

