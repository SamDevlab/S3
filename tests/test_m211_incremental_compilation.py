from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.build_graph import BuildGraph
from bootstrap.s3.incremental_build import (
    IncrementalArtifact,
    IncrementalBuildError,
    IncrementalProvenance,
    artifact_matches,
    load_incremental_artifact,
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
"""


def _graph(root: Path) -> BuildGraph:
    root.mkdir()
    (root / "s3.toml").write_text(MANIFEST, encoding="utf-8")
    (root / "main.s3").write_text("fn main() -> tryte:\n    return 1\n", encoding="utf-8")
    return BuildGraph.from_toml(root / "s3.toml")


def test_incremental_artifact_is_content_addressed_and_round_trips(tmp_path: Path) -> None:
    graph = _graph(tmp_path / "project")
    provenance = IncrementalProvenance("compiler-sha", "linux-x86_64", "assembly", "O1")
    artifact = IncrementalArtifact.create(
        graph,
        provenance,
        semantic_digest="semantic-a",
        assembly_digest="assembly-a",
        program_result="1",
    )
    path = tmp_path / "artifact.json"
    artifact.write(path)
    loaded = load_incremental_artifact(path)
    assert loaded == artifact
    assert artifact_matches(loaded, graph, provenance)
    assert "project" not in loaded.text


def test_incremental_artifact_rejects_corrupt_output_digest(tmp_path: Path) -> None:
    graph = _graph(tmp_path / "project")
    artifact = IncrementalArtifact.create(
        graph,
        IncrementalProvenance("compiler-sha", "linux-x86_64", "assembly", "O1"),
        semantic_digest="semantic-a",
        assembly_digest="assembly-a",
        program_result="1",
    )
    path = tmp_path / "artifact.json"
    path.write_text(artifact.text.replace(artifact.output_digest, "0" * 64), encoding="utf-8")
    with pytest.raises(IncrementalBuildError, match="output digest mismatch"):
        load_incremental_artifact(path)


def test_incremental_artifact_misses_on_provenance_or_graph_change(tmp_path: Path) -> None:
    graph = _graph(tmp_path / "project")
    provenance = IncrementalProvenance("compiler-sha", "linux-x86_64", "assembly", "O1")
    artifact = IncrementalArtifact.create(
        graph,
        provenance,
        semantic_digest="semantic-a",
        assembly_digest="assembly-a",
        program_result="1",
    )
    assert not artifact_matches(
        artifact,
        graph,
        IncrementalProvenance("other-compiler", "linux-x86_64", "assembly", "O1"),
    )
    (tmp_path / "project" / "main.s3").write_text("fn main() -> tryte:\n    return 2\n", encoding="utf-8")
    changed = BuildGraph.from_toml(tmp_path / "project" / "s3.toml")
    assert not artifact_matches(artifact, changed, provenance)
