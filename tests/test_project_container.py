from __future__ import annotations

import pytest

from bootstrap.s3.project_container import (
    ProjectContainer,
    ProjectContainerError,
    ProjectUnit,
    CapabilityState,
    ProjectTooling,
)


def test_project_container_manifest_is_deterministic() -> None:
    container = ProjectContainer(
        "demo",
        (
            ProjectUnit("core", ("main.s3", "util.s3")),
            ProjectUnit("tests", ("smoke.s3",)),
        ),
    )
    assert container.manifest == (
        ("core", ("main.s3", "util.s3")),
        ("tests", ("smoke.s3",)),
    )
    assert len(container.manifest_sha256) == 64


def test_project_container_rejects_duplicate_or_unsorted_units() -> None:
    unit = ProjectUnit("core", ("main.s3",))
    with pytest.raises(ProjectContainerError, match="sorted"):
        ProjectContainer("demo", (ProjectUnit("tests", ("t.s3",)), unit))
    with pytest.raises(ProjectContainerError, match="unique"):
        ProjectContainer("demo", (unit, unit))


def test_project_unit_requires_sorted_unique_sources() -> None:
    with pytest.raises(ProjectContainerError, match="sorted and unique"):
        ProjectUnit("core", ("z.s3", "a.s3"))


def test_external_project_manifest_check_inspect_build_run_and_plan(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.s3").write_text(
        "module main\n\nfn main() -> i64:\n    return 42\n", encoding="ascii"
    )
    (tmp_path / "s3.toml").write_text(
        """\
[project]
name = "scientific_app"
version = "1.0.0"
entrypoint = "main"
source_roots = ["src"]
profile = "hosted"
dependencies = []
foreign_libraries = ["libm"]
external_executables = ["helper"]
services = ["filesystem"]

[project.environment]
MODE = "test"

[capabilities]
"filesystem.read" = true
"process.spawn" = false

[container]
base = "ubuntu"
""",
        encoding="ascii",
    )
    tooling = ProjectTooling(tmp_path)
    manifest = tooling.check()
    assert manifest.name == "scientific_app"
    assert manifest.capability_map["filesystem.read"] is CapabilityState.ENFORCED
    assert tooling.inspect()["sources"] == ("src/main.s3",)
    assert tooling.build().assembly.functions
    assert tooling.run() == 42
    plan = tooling.container_plan()
    assert plan["kind"] == "s3.container.plan.v1"
    assert plan["capabilities"] == {"filesystem.read": "enforced", "process.spawn": "declared"}


def test_manifest_rejects_missing_source_root(tmp_path) -> None:
    (tmp_path / "s3.toml").write_text(
        "[project]\nname='x'\nversion='1'\nentrypoint='main'\nsource_roots=['missing']\nprofile='hosted'\n",
        encoding="ascii",
    )
    with pytest.raises(ProjectContainerError, match="source root"):
        ProjectTooling(tmp_path).check()
