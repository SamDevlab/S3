"""Content-addressed incremental build planning for M1.57."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .build_graph import BuildGraph, BuildGraphError


class IncrementalBuildError(ValueError):
    """Raised when persisted incremental state is malformed."""


@dataclass(frozen=True, slots=True)
class IncrementalBuildState:
    graph_identity: str
    unit_identities: tuple[tuple[str, str], ...]

    @classmethod
    def from_graph(cls, graph: BuildGraph) -> "IncrementalBuildState":
        identities = graph.unit_artifact_identities
        return cls(graph.artifact_identity, tuple(sorted(identities.items())))

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "IncrementalBuildState":
        if payload.get("format") != "s3.incremental-state.v1":
            raise IncrementalBuildError("unsupported incremental state format")
        graph_identity = payload.get("graph_identity")
        raw_units = payload.get("unit_identities")
        if not isinstance(graph_identity, str) or not graph_identity:
            raise IncrementalBuildError("incremental state requires graph_identity")
        if not isinstance(raw_units, dict):
            raise IncrementalBuildError("incremental state requires unit_identities")
        units: list[tuple[str, str]] = []
        for name, identity in raw_units.items():
            if not isinstance(name, str) or not isinstance(identity, str) or not identity:
                raise IncrementalBuildError("unit identities must be non-empty strings")
            units.append((name, identity))
        return cls(graph_identity, tuple(sorted(units)))

    @property
    def payload(self) -> dict[str, object]:
        return {
            "format": "s3.incremental-state.v1",
            "graph_identity": self.graph_identity,
            "unit_identities": dict(self.unit_identities),
        }

    @property
    def text(self) -> str:
        return json.dumps(self.payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.text, encoding="utf-8", newline="\n")


@dataclass(frozen=True, slots=True)
class IncrementalBuildPlan:
    graph_identity: str
    rebuilt_units: tuple[str, ...]
    reused_units: tuple[str, ...]

    @property
    def cold(self) -> bool:
        return not self.reused_units


def plan_incremental_build(
    graph: BuildGraph,
    previous: IncrementalBuildState | None = None,
) -> IncrementalBuildPlan:
    current = graph.unit_artifact_identities
    previous_units = dict(previous.unit_identities) if previous is not None else {}
    rebuilt = tuple(
        name for name in graph.topological_order
        if previous_units.get(name) != current[name]
    )
    reused = tuple(
        name for name in graph.topological_order
        if previous_units.get(name) == current[name]
    )
    return IncrementalBuildPlan(graph.artifact_identity, rebuilt, reused)


def load_incremental_state(path: str | Path) -> IncrementalBuildState:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IncrementalBuildError(f"could not read incremental state {path}") from error
    if not isinstance(payload, dict):
        raise IncrementalBuildError("incremental state must be an object")
    return IncrementalBuildState.from_payload(payload)
