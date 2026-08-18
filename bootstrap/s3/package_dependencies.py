"""Deterministic local package dependency resolution for M1.56."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Mapping


class PackageDependencyError(ValueError):
    """Raised when a package manifest or dependency graph is invalid."""


_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_REVISION = re.compile(r"^[0-9a-fA-F]{7,64}$")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _name(value: object, field: str) -> str:
    if not isinstance(value, str) or _NAME.fullmatch(value) is None:
        raise PackageDependencyError(f"invalid {field} {value!r}")
    return value


def _relative_source(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PackageDependencyError("dependency source must be non-empty")
    normalized = value.replace("\\", "/")
    if "://" in normalized or normalized.startswith("git+"):
        return normalized
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise PackageDependencyError("local dependency source must stay relative")
    return "/".join(path.parts)


@dataclass(frozen=True, slots=True)
class PackageDependency:
    name: str
    source: str
    revision: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _name(self.name, "dependency name"))
        object.__setattr__(self, "source", _relative_source(self.source))
        if self.revision is not None and _REVISION.fullmatch(self.revision) is None:
            raise PackageDependencyError("dependency revision must be a hexadecimal commit id")
        if (self.source.startswith("git+") or "://" in self.source) and self.revision is None:
            raise PackageDependencyError("Git dependencies require an immutable revision")


@dataclass(frozen=True, slots=True)
class PackageManifest:
    name: str
    version: str
    dependencies: tuple[PackageDependency, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _name(self.name, "package name"))
        if not isinstance(self.version, str) or not self.version:
            raise PackageDependencyError("package version must be non-empty")
        names = tuple(item.name for item in self.dependencies)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise PackageDependencyError("package dependencies must be sorted and unique")

    @property
    def payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "dependencies": [
                {
                    "name": item.name,
                    "source": item.source,
                    "revision": item.revision,
                }
                for item in self.dependencies
            ],
        }

    @property
    def content_sha256(self) -> str:
        return _sha256(_canonical_json(self.payload))


def parse_package_manifest(path: str) -> PackageManifest:
    """Parse a package.toml manifest without consulting the network."""

    try:
        raw = tomllib.loads(open(path, "rb").read().decode("utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise PackageDependencyError(f"could not parse package manifest {path}") from error
    package = raw.get("package")
    if not isinstance(package, dict):
        raise PackageDependencyError("package.toml requires a [package] table")
    raw_dependencies = raw.get("dependency", [])
    if not isinstance(raw_dependencies, list):
        raise PackageDependencyError("dependency entries must be tables")
    dependencies = []
    for raw_dependency in raw_dependencies:
        if not isinstance(raw_dependency, dict):
            raise PackageDependencyError("each [[dependency]] must be a table")
        dependencies.append(
            PackageDependency(
                _name(raw_dependency.get("name"), "dependency name"),
                raw_dependency.get("source"),
                raw_dependency.get("revision"),
            )
        )
    return PackageManifest(
        _name(package.get("name"), "package name"),
        package.get("version"),
        tuple(sorted(dependencies, key=lambda item: item.name)),
    )


@dataclass(frozen=True, slots=True)
class PackageLockEntry:
    name: str
    version: str
    source: str
    revision: str | None
    content_sha256: str

    @property
    def payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "revision": self.revision,
            "content_sha256": self.content_sha256,
        }


@dataclass(frozen=True, slots=True)
class PackageLock:
    root: str
    topological_order: tuple[str, ...]
    entries: tuple[PackageLockEntry, ...]

    @classmethod
    def resolve(
        cls,
        root: str,
        manifests: Mapping[str, PackageManifest],
    ) -> "PackageLock":
        root = _name(root, "root package name")
        if root not in manifests:
            raise PackageDependencyError(f"missing root package '{root}'")
        for name, manifest in manifests.items():
            if name != manifest.name:
                raise PackageDependencyError(
                    f"manifest key '{name}' does not match package '{manifest.name}'"
                )
        states: dict[str, int] = {}
        order: list[str] = []
        reachable_references: dict[str, list[PackageDependency]] = {}

        def visit(name: str, stack: tuple[str, ...]) -> None:
            state = states.get(name, 0)
            if state == 2:
                return
            if state == 1:
                cycle = " -> ".join((*stack, name))
                raise PackageDependencyError(f"package dependency cycle: {cycle}")
            manifest = manifests.get(name)
            if manifest is None:
                raise PackageDependencyError(f"missing package dependency '{name}'")
            states[name] = 1
            for dependency in manifest.dependencies:
                reachable_references.setdefault(dependency.name, []).append(dependency)
                visit(dependency.name, (*stack, name))
            states[name] = 2
            order.append(name)

        visit(root, ())
        entries: list[PackageLockEntry] = []
        for name in order:
            manifest = manifests[name]
            if name == root:
                source = "."
                revision = None
            else:
                references = reachable_references.get(name, [])
                if not references:
                    raise PackageDependencyError(
                        f"missing dependency identity for package '{name}'"
                    )
                identity = (references[0].source, references[0].revision)
                if any((item.source, item.revision) != identity for item in references[1:]):
                    raise PackageDependencyError(
                        f"inconsistent dependency identity for package '{name}'"
                    )
                source, revision = identity
            entries.append(
                PackageLockEntry(
                    name,
                    manifest.version,
                    source,
                    revision,
                    manifest.content_sha256,
                )
            )
        return cls(root, tuple(order), tuple(entries))

    @property
    def payload(self) -> dict[str, object]:
        return {
            "format": "s3.package-lock.v1",
            "root": self.root,
            "topological_order": list(self.topological_order),
            "packages": [entry.payload for entry in self.entries],
        }

    @property
    def text(self) -> str:
        return json.dumps(self.payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"

    @property
    def sha256(self) -> str:
        return _sha256(self.text)
