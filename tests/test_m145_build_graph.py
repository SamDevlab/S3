from __future__ import annotations

import hashlib
import json

import pytest

from bootstrap.s3.build_graph import BuildGraph, BuildGraphError
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.pipeline import compile_sources


MANIFEST = """\
[project]
name = "demo"
root = "."
target = "linux-x86_64"
profile = "debug"

[profiles.debug]
optimization = "O1"

[[unit]]
name = "app"
path = "."
sources = ["main.s3"]
dependencies = ["math"]

[[unit]]
name = "math"
path = "math"
sources = ["math.s3"]

[[foreign_library]]
name = "libc"
target = "linux-x86_64"
kind = "system"
"""


MAIN = """\
module main
from math import inc
fn main() -> tryte:
    return inc(1)
"""


MATH = """\
module math
export fn inc(value: tryte) -> tryte:
    return value + 1
"""


def _write_project(path, manifest: str = MANIFEST):
    (path / "math").mkdir(parents=True)
    (path / "s3.toml").write_text(manifest, encoding="utf-8")
    (path / "main.s3").write_text(MAIN, encoding="utf-8")
    (path / "math" / "math.s3").write_text(MATH, encoding="utf-8")
    return path / "s3.toml"


def test_graph_lock_and_topological_plan_are_reproducible(tmp_path) -> None:
    first = BuildGraph.from_toml(_write_project(tmp_path / "first"))
    second = BuildGraph.from_toml(_write_project(tmp_path / "second"))

    assert first.topological_order == ("math", "app")
    assert first.lockfile_text == second.lockfile_text
    assert first.lockfile_sha256 == second.lockfile_sha256
    assert first.artifact_identity == second.artifact_identity
    assert tuple(step.unit_name for step in first.build_plan) == ("math", "app")
    assert first.target_profile.optimization == "O1"


def test_lockfile_is_content_hashed_and_matches_independent_manifest(tmp_path) -> None:
    manifest = _write_project(tmp_path / "project")
    graph = BuildGraph.from_toml(manifest)
    source_hash = hashlib.sha256(
        (tmp_path / "project" / "math" / "math.s3").read_bytes()
    ).hexdigest()
    payload = graph.lockfile_payload
    math_record = next(item for item in payload["units"] if item["name"] == "math")

    assert math_record["sources"] == [{"path": "math.s3", "sha256": source_hash}]
    assert json.loads(graph.lockfile_text) == payload
    assert graph.lockfile_sha256 == hashlib.sha256(graph.lockfile_text.encode()).hexdigest()

    (tmp_path / "project" / "math" / "math.s3").write_text(
        MATH.replace("value + 1", "value + 2"), encoding="utf-8"
    )
    changed = BuildGraph.from_toml(manifest)
    assert changed.graph_sha256 != graph.graph_sha256
    assert changed.artifact_identity != graph.artifact_identity


def test_graph_sources_compile_in_isolated_topological_order(tmp_path) -> None:
    graph = BuildGraph.from_toml(_write_project(tmp_path / "project"))
    sources = graph.load_sources()
    result = compile_sources(sources, graph.target_profile.optimization)

    assert execute_ir(result.ir) == 2
    assert tuple(sources) == ("math/math.s3", "app/main.s3")


def test_missing_and_cyclic_dependencies_are_rejected(tmp_path) -> None:
    missing = MANIFEST.replace('dependencies = ["math"]', 'dependencies = ["absent"]')
    with pytest.raises(BuildGraphError, match="missing dependency 'absent'"):
        BuildGraph.from_toml(_write_project(tmp_path / "missing", missing))

    cyclic = MANIFEST.replace('dependencies = ["math"]', 'dependencies = ["math"]')
    cyclic = cyclic.replace(
        'path = "math"\nsources = ["math.s3"]\n',
        'path = "math"\nsources = ["math.s3"]\ndependencies = ["app"]\n',
    )
    with pytest.raises(BuildGraphError, match="dependency cycle"):
        BuildGraph.from_toml(_write_project(tmp_path / "cycle", cyclic))


def test_target_and_path_boundaries_are_rejected(tmp_path) -> None:
    unsupported = MANIFEST.replace('target = "linux-x86_64"', 'target = "windows-x86_64"')
    with pytest.raises(BuildGraphError, match="unsupported target"):
        BuildGraph.from_toml(_write_project(tmp_path / "target", unsupported))

    escaping = MANIFEST.replace('path = "math"', 'path = "../outside"')
    with pytest.raises(BuildGraphError, match="inside the project root"):
        BuildGraph.from_toml(_write_project(tmp_path / "escape", escaping))


def test_foreign_library_declaration_is_explicit_and_bound_to_unit(tmp_path) -> None:
    manifest = MANIFEST.replace(
        'dependencies = ["math"]',
        'dependencies = ["math"]\nforeign_libraries = ["libc"]',
    )
    graph = BuildGraph.from_toml(_write_project(tmp_path / "foreign", manifest))
    assert graph.lockfile_payload["foreign_libraries"] == [
        {"kind": "system", "name": "libc", "path": None, "sha256": None, "target": "linux-x86_64"}
    ]
