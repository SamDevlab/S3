from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.workspace import Workspace, WorkspaceError


MANIFEST = """
[project]
name = "{name}"
root = "."
target = "linux-x86_64"
profile = "debug"

[profiles.debug]
optimization = "O0"

[[unit]]
name = "main"
path = "."
sources = ["main.s3"]
"""


def _member(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir(parents=True)
    (path / "s3.toml").write_text(MANIFEST.format(name=name), encoding="utf-8")
    (path / "main.s3").write_text("fn main() -> tryte:\n    return 1\n", encoding="utf-8")
    return path / "s3.toml"


def test_workspace_resolution_is_path_independent_and_topologically_sorted(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _member(first_root, "app")
    _member(first_root, "core")
    _member(second_root, "app")
    _member(second_root, "core")
    first = Workspace.from_manifests(first_root, (Path("app/s3.toml"), Path("core/s3.toml")), dependencies={"app": ("core",)})
    second = Workspace.from_manifests(second_root, (Path("core/s3.toml"), Path("app/s3.toml")), dependencies={"app": ("core",)})
    assert first.topological_order == ("core", "app")
    assert first.resolution_digest == second.resolution_digest


def test_workspace_rejects_unknown_duplicates_and_cycles(tmp_path: Path) -> None:
    _member(tmp_path, "app")
    _member(tmp_path, "core")
    with pytest.raises(WorkspaceError, match="unknown package"):
        Workspace.from_manifests(tmp_path, ("app/s3.toml", "core/s3.toml"), dependencies={"app": ("missing",)})
    with pytest.raises(WorkspaceError, match="cycle"):
        Workspace.from_manifests(tmp_path, ("app/s3.toml", "core/s3.toml"), dependencies={"app": ("core",), "core": ("app",)})
    duplicate = tmp_path / "duplicate"
    duplicate.mkdir()
    (duplicate / "s3.toml").write_text(MANIFEST.format(name="app"), encoding="utf-8")
    (duplicate / "main.s3").write_text("fn main() -> tryte:\n    return 1\n", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="sorted and unique"):
        Workspace.from_manifests(tmp_path, ("app/s3.toml", "duplicate/s3.toml"))
