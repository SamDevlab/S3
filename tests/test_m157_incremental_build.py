from __future__ import annotations

from pathlib import Path

from bootstrap.s3.build_graph import BuildGraph
from bootstrap.s3.incremental_build import (
    IncrementalBuildState,
    load_incremental_state,
    plan_incremental_build,
)


MANIFEST = """
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
"""


def _project(root: Path) -> Path:
    (root / "math").mkdir(parents=True)
    (root / "s3.toml").write_text(MANIFEST, encoding="utf-8")
    (root / "main.s3").write_text(
        "module main\nfrom math import inc\nfn main() -> tryte:\n    return inc(1)\n",
        encoding="utf-8",
    )
    (root / "math" / "math.s3").write_text(
        "module math\nexport fn inc(value: tryte) -> tryte:\n    return value + 1\n",
        encoding="utf-8",
    )
    return root / "s3.toml"


def test_cold_then_warm_plan_reuses_all_content_identical_units(tmp_path: Path) -> None:
    graph = BuildGraph.from_toml(_project(tmp_path / "project"))
    cold = plan_incremental_build(graph)
    assert cold.cold
    assert cold.rebuilt_units == ("math", "app")

    state = IncrementalBuildState.from_graph(graph)
    warm = plan_incremental_build(graph, state)
    assert not warm.cold
    assert warm.rebuilt_units == ()
    assert warm.reused_units == ("math", "app")


def test_dependency_change_invalidates_dependents_but_not_unrelated_units(tmp_path: Path) -> None:
    manifest = _project(tmp_path / "project")
    first = BuildGraph.from_toml(manifest)
    state = IncrementalBuildState.from_graph(first)
    (tmp_path / "project" / "math" / "math.s3").write_text(
        "module math\nexport fn inc(value: tryte) -> tryte:\n    return value + 2\n",
        encoding="utf-8",
    )
    changed = BuildGraph.from_toml(manifest)
    plan = plan_incremental_build(changed, state)
    assert plan.rebuilt_units == ("math", "app")
    assert plan.reused_units == ()


def test_state_round_trip_is_path_and_timestamp_free(tmp_path: Path) -> None:
    graph = BuildGraph.from_toml(_project(tmp_path / "project"))
    state_path = tmp_path / "state.json"
    state = IncrementalBuildState.from_graph(graph)
    state.write(state_path)
    assert load_incremental_state(state_path) == state
    assert str(tmp_path) not in state.text
    assert "timestamp" not in state.text
