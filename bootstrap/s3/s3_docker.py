"""Deterministic Docker execution contract for M1.38."""

from __future__ import annotations

import re
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


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


@dataclass(frozen=True, slots=True)
class DockerResult:
    """Stable result surface for a Docker CLI operation."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


Runner = Callable[..., subprocess.CompletedProcess[str]]


class DockerProvider:
    """Concrete Docker CLI provider with daemonless planning operations.

    The provider is deliberately small and injectable: production uses
    ``subprocess.run`` while tests can record the exact argv and return a
    deterministic result without a Docker daemon.
    """

    def __init__(self, executable: str = "docker", runner: Runner = subprocess.run) -> None:
        if not executable or Path(executable).name != executable:
            raise DockerConfigError("Docker executable must be a simple command name")
        self.executable = executable
        self._runner = runner

    def _run(self, args: Sequence[str], *, cwd: Path | None = None) -> DockerResult:
        argv = (self.executable, *tuple(args))
        completed = self._runner(
            argv,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            check=False,
        )
        return DockerResult(
            argv,
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )

    def version(self) -> DockerResult:
        return self._run(("version", "--format", "{{.Server.Version}}"))

    def inspect(self, image: str) -> DockerResult:
        if not _IMAGE.fullmatch(image):
            raise DockerConfigError(f"invalid Docker image {image!r}")
        return self._run(("image", "inspect", image))

    def build(self, context: Path, tag: str, *, dockerfile: str = "Dockerfile") -> DockerResult:
        if not context.is_dir():
            raise DockerConfigError("Docker build context must be a directory")
        if not _IMAGE.fullmatch(tag):
            raise DockerConfigError(f"invalid Docker image {tag!r}")
        return self._run(("build", "--file", dockerfile, "--tag", tag, "."), cwd=context)

    def run(self, spec: DockerSpec) -> DockerResult:
        args = ["run", "--rm"]
        args.extend(f"--env={name}={value}" for name, value in spec.environment)
        args.extend((spec.image, *spec.command))
        return self._run(tuple(args))

    def plan(self, spec: DockerSpec) -> dict[str, object]:
        return {
            "kind": "s3.docker.plan.v1",
            "provider": "docker-cli",
            "argv": spec.argv,
            "environment": spec.environment,
            "timeout_seconds": spec.timeout_seconds,
        }

    def write_deterministic_context(
        self,
        root: Path,
        *,
        image: str,
        entrypoint: Sequence[str],
        source_files: dict[str, str],
        foreign_helpers: dict[str, str] | None = None,
    ) -> Path:
        """Materialize a reproducible Docker build context and recipe."""

        if not _IMAGE.fullmatch(image):
            raise DockerConfigError(f"invalid Docker image {image!r}")
        if not entrypoint or any(not item for item in entrypoint):
            raise DockerConfigError("container entrypoint must be non-empty")
        foreign_helpers = {} if foreign_helpers is None else foreign_helpers
        if any(not _ENV_NAME.fullmatch(name) for name in foreign_helpers):
            raise DockerConfigError("foreign helper names must be valid identifiers")
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        for logical_name in sorted(source_files):
            target = root / logical_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source_files[logical_name], encoding="utf-8", newline="\n")
        helper_root = root / "foreign"
        helper_root.mkdir(parents=True, exist_ok=True)
        for name in sorted(foreign_helpers):
            helper = helper_root / name
            helper.parent.mkdir(parents=True, exist_ok=True)
            helper.write_text(foreign_helpers[name], encoding="utf-8", newline="\n")
        recipe = (
            "FROM " + image + "\n"
            "WORKDIR /app\n"
            "COPY . /app\n"
            "COPY foreign /opt/s3/foreign\n"
            "RUN chmod +x /opt/s3/foreign/*\n"
            "ENTRYPOINT " + json.dumps(list(entrypoint), separators=(",", ":")) + "\n"
        )
        (root / "Dockerfile").write_text(recipe, encoding="utf-8", newline="\n")
        return root

    def project_build_context(
        self,
        source_files: dict[str, str],
        *,
        image: str,
        entrypoint: Sequence[str],
        foreign_helpers: dict[str, str] | None = None,
    ) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        temporary = tempfile.TemporaryDirectory(prefix="s3-docker-")
        context = self.write_deterministic_context(
            Path(temporary.name),
            image=image,
            entrypoint=entrypoint,
            source_files=source_files,
            foreign_helpers=foreign_helpers,
        )
        return context, temporary

