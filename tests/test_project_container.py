from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from bootstrap.s3.project_container import (
    ProjectContainer,
    ProjectContainerError,
    ProjectUnit,
    CapabilityState,
    ProjectTooling,
)
from bootstrap.s3.s3_docker import DockerProvider


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


def test_project_tooling_forwards_explicit_compiler_to_shared_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "src").mkdir()
    source = "module main\nfn main() -> i64:\n    return 7\n"
    (tmp_path / "src" / "main.s3").write_text(source, encoding="ascii")
    (tmp_path / "s3.toml").write_text(
        "[project]\nname='app'\nversion='1'\nentrypoint='main'\n"
        "source_roots=['src']\nprofile='hosted'\n",
        encoding="ascii",
    )
    calls: list[dict[str, object]] = []
    fake_ir = object()
    fake_assembly = SimpleNamespace(functions=())

    def fake_compile(sources, **kwargs):
        calls.append({"sources": sources, **kwargs})
        return SimpleNamespace(
            ir=fake_ir,
            assembly=fake_assembly,
            require_ordinary_artifacts=lambda: (fake_ir, fake_assembly),
        )

    monkeypatch.setattr(
        "bootstrap.s3.project_container.compile_source_set_with_provider",
        fake_compile,
    )
    executable = tmp_path / "s3c-ng"
    tooling = ProjectTooling(
        tmp_path,
        compiler="s3c-ng",
        executable=executable,
        container_executable="/opt/s3/s3c-ng",
    )

    assert tooling.build().ir is fake_ir
    assert tooling.container_run_command() == (
        "s3",
        "run",
        "/app/main.s3",
        "--compiler",
        "s3c-ng",
        "--s3c-ng-executable",
        "/opt/s3/s3c-ng",
    )
    assert calls == [
        {
            "sources": {"src/main.s3": source},
            "compiler": "s3c-ng",
            "executable": executable,
            "entry_module": "main",
        }
    ]


def test_project_docker_context_embeds_selected_runtime_compiler(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.s3").write_text(
        "module main\nfn main() -> i64:\n    return 7\n", encoding="ascii"
    )
    (tmp_path / "s3.toml").write_text(
        "[project]\nname='app'\nversion='1'\nentrypoint='main'\n"
        "source_roots=['src']\nprofile='hosted'\n",
        encoding="ascii",
    )
    tooling = ProjectTooling(
        tmp_path,
        compiler="s3c-ng",
        container_executable="/opt/s3/s3c-ng",
    )
    context, owner = tooling.docker_context(DockerProvider(), image="s3/runtime:1.38")
    try:
        assert (context / "Dockerfile").read_text(encoding="ascii").endswith(
            'ENTRYPOINT ["s3","run","/app/main.s3","--compiler","s3c-ng",'
            '"--s3c-ng-executable","/opt/s3/s3c-ng"]\n'
        )
    finally:
        owner.cleanup()


def test_manifest_rejects_missing_source_root(tmp_path) -> None:
    (tmp_path / "s3.toml").write_text(
        "[project]\nname='x'\nversion='1'\nentrypoint='main'\nsource_roots=['missing']\nprofile='hosted'\n",
        encoding="ascii",
    )
    with pytest.raises(ProjectContainerError, match="source root"):
        ProjectTooling(tmp_path).check()


def test_project_docker_context_contains_real_project_sources(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.s3").write_text(
        "module main\n\nfn main() -> i64:\n    return 7\n", encoding="ascii"
    )
    (tmp_path / "s3.toml").write_text(
        "[project]\nname='app'\nversion='1'\nentrypoint='main'\n"
        "source_roots=['src']\nprofile='hosted'\n",
        encoding="ascii",
    )
    tooling = ProjectTooling(tmp_path)
    context, owner = tooling.docker_context(DockerProvider(), image="s3/runtime:1.38")
    try:
        assert (context / "src" / "main.s3").read_text(encoding="ascii").endswith("return 7\n")
        assert (context / "Dockerfile").read_text(encoding="ascii").startswith("FROM s3/runtime:1.38\n")
    finally:
        owner.cleanup()
