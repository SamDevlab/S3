"""Deterministic multi-package workspace model built on existing s3.toml graphs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

from .build_graph import BuildGraph, BuildGraphError


class WorkspaceError(ValueError):
    """Raised when a workspace cannot be resolved safely."""


def _digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _relative(root: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise WorkspaceError("workspace manifest must stay inside workspace root") from error
    normalized = PurePosixPath(relative.as_posix())
    if normalized == PurePosixPath(".") or ".." in normalized.parts:
        raise WorkspaceError("workspace manifest path is invalid")
    return normalized.as_posix()


@dataclass(frozen=True, slots=True)
class WorkspaceMember:
    name: str
    manifest: str
    graph_identity: str
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not self.manifest or not self.graph_identity:
            raise WorkspaceError("workspace member identity is incomplete")
        if tuple(sorted(set(self.dependencies))) != self.dependencies:
            raise WorkspaceError("workspace dependencies must be sorted and unique")


@dataclass(frozen=True, slots=True)
class Workspace:
    root: Path
    members: tuple[WorkspaceMember, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root).resolve())
        names = tuple(item.name for item in self.members)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise WorkspaceError("workspace member identities must be sorted and unique")
        known = set(names)
        for member in self.members:
            unknown = set(member.dependencies) - known
            if unknown:
                raise WorkspaceError(f"workspace member {member.name!r} depends on unknown package {sorted(unknown)[0]!r}")
        self.topological_order

    @classmethod
    def from_manifests(
        cls,
        root: str | Path,
        manifests: tuple[str | Path, ...],
        *,
        dependencies: Mapping[str, tuple[str, ...]] | None = None,
    ) -> "Workspace":
        workspace_root = Path(root).resolve()
        if not manifests:
            raise WorkspaceError("workspace requires at least one manifest")
        dependency_map = dependencies or {}
        members: list[WorkspaceMember] = []
        for manifest_value in manifests:
            manifest = (workspace_root / manifest_value).resolve()
            relative = _relative(workspace_root, manifest)
            try:
                graph = BuildGraph.from_toml(manifest)
            except (OSError, BuildGraphError) as error:
                raise WorkspaceError(f"cannot load workspace member {relative}") from error
            deps = dependency_map.get(graph.name, ())
            if not isinstance(deps, tuple) or any(not isinstance(value, str) for value in deps):
                raise WorkspaceError(f"dependencies for {graph.name!r} must be a tuple of names")
            members.append(WorkspaceMember(graph.name, relative, graph.artifact_identity, tuple(sorted(deps))))
        candidate = cls(workspace_root, tuple(sorted(members, key=lambda item: item.name)))
        return candidate

    @property
    def topological_order(self) -> tuple[str, ...]:
        members = {item.name: item for item in self.members}
        remaining = {name: len(item.dependencies) for name, item in members.items()}
        reverse = {name: [] for name in members}
        for item in self.members:
            for dependency in item.dependencies:
                reverse[dependency].append(item.name)
        ready = sorted(name for name, count in remaining.items() if count == 0)
        result: list[str] = []
        while ready:
            name = ready.pop(0)
            result.append(name)
            for dependent in sorted(reverse[name]):
                remaining[dependent] -= 1
                if remaining[dependent] == 0:
                    ready.append(dependent)
                    ready.sort()
        if len(result) != len(members):
            raise WorkspaceError("workspace dependency cycle detected")
        return tuple(result)

    @property
    def resolution_payload(self) -> dict[str, object]:
        return {
            "format": "s3.workspace.v1",
            "members": [
                {
                    "name": item.name,
                    "manifest": item.manifest,
                    "graph_identity": item.graph_identity,
                    "dependencies": list(item.dependencies),
                }
                for item in self.members
            ],
            "topological_order": list(self.topological_order),
        }

    @property
    def resolution_digest(self) -> str:
        return _digest(self.resolution_payload)
