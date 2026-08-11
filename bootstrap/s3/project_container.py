"""Deterministic project-container model for M1.37."""

from __future__ import annotations

import hashlib
import re
import tomllib
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class ProjectContainerError(ValueError):
    """Raised when a project container violates its structural contract."""


class CapabilityState(Enum):
    DECLARED = "declared"
    ENFORCED = "enforced"


@dataclass(frozen=True, slots=True)
class ProjectManifest:
    name: str
    version: str
    entrypoint: str
    source_roots: tuple[str, ...]
    profile: str
    dependencies: tuple[str, ...]
    foreign_libraries: tuple[str, ...]
    external_executables: tuple[str, ...]
    environment: tuple[tuple[str, str], ...]
    capabilities: tuple[tuple[str, CapabilityState], ...]
    services: tuple[str, ...]
    container: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not _NAME.fullmatch(self.name):
            raise ProjectContainerError(f"invalid project name {self.name!r}")
        if self.profile not in {"freestanding", "hosted"}:
            raise ProjectContainerError("profile must be 'freestanding' or 'hosted'")
        if not self.entrypoint:
            raise ProjectContainerError("entrypoint must not be empty")
        if tuple(sorted(set(self.source_roots))) != self.source_roots:
            raise ProjectContainerError("source roots must be sorted and unique")

    @property
    def capability_map(self) -> dict[str, CapabilityState]:
        return dict(self.capabilities)


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ProjectContainerError(f"{field} must be a list of non-empty strings")
    return tuple(sorted(set(value)))


def parse_manifest(path: Path) -> ProjectManifest:
    """Parse and validate a deterministic ``s3.toml`` project manifest."""

    try:
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ProjectContainerError(f"could not parse manifest {path}") from error
    project = raw.get("project")
    if not isinstance(project, dict):
        raise ProjectContainerError("manifest requires a [project] table")
    capabilities_raw = raw.get("capabilities", {})
    if not isinstance(capabilities_raw, dict):
        raise ProjectContainerError("capabilities must be a table")
    capabilities = tuple(
        sorted(
            (
                str(name),
                CapabilityState.ENFORCED if bool(enforced) else CapabilityState.DECLARED,
            )
            for name, enforced in capabilities_raw.items()
        )
    )
    environment_raw = project.get("environment", {})
    if not isinstance(environment_raw, dict):
        raise ProjectContainerError("project.environment must be a table")
    container_raw = raw.get("container", {})
    if not isinstance(container_raw, dict):
        raise ProjectContainerError("container must be a table")
    return ProjectManifest(
        str(project.get("name", "")),
        str(project.get("version", "")),
        str(project.get("entrypoint", "main")),
        _string_tuple(project.get("source_roots", ["src"]), "source_roots"),
        str(project.get("profile", "hosted")),
        _string_tuple(project.get("dependencies", []), "dependencies"),
        _string_tuple(project.get("foreign_libraries", []), "foreign_libraries"),
        _string_tuple(project.get("external_executables", []), "external_executables"),
        tuple(sorted((str(key), str(value)) for key, value in environment_raw.items())),
        capabilities,
        _string_tuple(project.get("services", []), "services"),
        tuple(sorted((str(key), str(value)) for key, value in container_raw.items())),
    )


class ProjectTooling:
    """Public daemonless project check/build/run/inspect/plan operations."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.manifest_path = self.root / "s3.toml"
        self.manifest = parse_manifest(self.manifest_path)

    def check(self) -> ProjectManifest:
        sources = self._sources()
        if not sources:
            raise ProjectContainerError("project has no .s3 source files")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", self.manifest.entrypoint):
            raise ProjectContainerError("invalid project entrypoint")
        return self.manifest

    def inspect(self) -> dict[str, object]:
        self.check()
        return {
            "name": self.manifest.name,
            "version": self.manifest.version,
            "entrypoint": self.manifest.entrypoint,
            "profile": self.manifest.profile,
            "sources": tuple(sorted(self._sources())),
            "capabilities": {
                name: state.value for name, state in self.manifest.capabilities
            },
        }

    def build(self):
        from .pipeline import compile_sources

        self.check()
        return compile_sources(self._sources(), entry_module="main")

    def run(self) -> int:
        from .emulator import Emulator

        compilation = self.build()
        return Emulator().execute(compilation.assembly, entry=self.manifest.entrypoint)

    def container_plan(self) -> dict[str, object]:
        self.check()
        return {
            "kind": "s3.container.plan.v1",
            "name": self.manifest.name,
            "version": self.manifest.version,
            "profile": self.manifest.profile,
            "entrypoint": self.manifest.entrypoint,
            "source_roots": self.manifest.source_roots,
            "capabilities": {
                name: state.value for name, state in self.manifest.capabilities
            },
            "foreign_libraries": self.manifest.foreign_libraries,
            "external_executables": self.manifest.external_executables,
        }

    def docker_context(self, provider, *, image: str) -> tuple[Path, object]:
        """Create a deterministic Docker context for this project.

        The returned temporary-directory owner must be kept alive while the
        context is used. The provider is injected so daemonless planning and
        real Docker execution share the same project serialization.
        """

        self.check()
        entrypoint = ("s3", "run", f"/app/{self.manifest.entrypoint}.s3")
        return provider.project_build_context(
            self._sources(), image=image, entrypoint=entrypoint
        )

    def _sources(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for root in self.manifest.source_roots:
            directory = self.root / root
            if not directory.is_dir():
                raise ProjectContainerError(f"source root does not exist: {root}")
            for source_path in sorted(directory.rglob("*.s3")):
                logical = source_path.relative_to(self.root).as_posix()
                result[logical] = source_path.read_text(encoding="utf-8")
        return result


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
