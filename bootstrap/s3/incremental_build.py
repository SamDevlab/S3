"""Content-addressed incremental build planning for M1.57."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .build_graph import BuildGraph, BuildGraphError


class IncrementalBuildError(ValueError):
    """Raised when persisted incremental state is malformed."""


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class IncrementalProvenance:
    """Immutable inputs that make a cache entry semantically reusable."""

    compiler: str
    target: str
    backend: str
    optimization: str
    language_config: str = "default"
    package_lock: str = "none"

    def __post_init__(self) -> None:
        values = (self.compiler, self.target, self.backend, self.optimization, self.language_config, self.package_lock)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise IncrementalBuildError("incremental provenance fields must be non-empty strings")

    @property
    def payload(self) -> dict[str, str]:
        return {
            "compiler": self.compiler,
            "target": self.target,
            "backend": self.backend,
            "optimization": self.optimization,
            "language_config": self.language_config,
            "package_lock": self.package_lock,
        }


@dataclass(frozen=True, slots=True)
class IncrementalArtifact:
    """A fail-closed cache envelope; the payload is never trusted by itself."""

    identity: str
    provenance: IncrementalProvenance
    output_digest: str
    semantic_digest: str
    assembly_digest: str
    program_result: str

    @classmethod
    def create(
        cls,
        graph: BuildGraph,
        provenance: IncrementalProvenance,
        *,
        semantic_digest: str,
        assembly_digest: str,
        program_result: str,
    ) -> "IncrementalArtifact":
        for name, value in (("semantic_digest", semantic_digest), ("assembly_digest", assembly_digest), ("program_result", program_result)):
            if not isinstance(value, str) or not value:
                raise IncrementalBuildError(f"{name} must be non-empty")
        identity = _digest({"graph": graph.artifact_identity, "provenance": provenance.payload})
        output_digest = _digest({"semantic": semantic_digest, "assembly": assembly_digest, "result": program_result})
        return cls(identity, provenance, output_digest, semantic_digest, assembly_digest, program_result)

    @property
    def payload(self) -> dict[str, object]:
        return {
            "format": "s3.incremental-artifact.v2",
            "identity": self.identity,
            "provenance": self.provenance.payload,
            "output_digest": self.output_digest,
            "semantic_digest": self.semantic_digest,
            "assembly_digest": self.assembly_digest,
            "program_result": self.program_result,
        }

    @property
    def text(self) -> str:
        return json.dumps(self.payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.text, encoding="utf-8", newline="\n")


def load_incremental_artifact(path: str | Path) -> IncrementalArtifact:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IncrementalBuildError(f"could not read incremental artifact {path}") from error
    if not isinstance(payload, dict) or payload.get("format") != "s3.incremental-artifact.v2":
        raise IncrementalBuildError("unsupported incremental artifact format")
    raw_provenance = payload.get("provenance")
    if not isinstance(raw_provenance, dict):
        raise IncrementalBuildError("incremental artifact provenance is missing")
    try:
        provenance = IncrementalProvenance(**raw_provenance)
        artifact = IncrementalArtifact(
            str(payload["identity"]),
            provenance,
            str(payload["output_digest"]),
            str(payload["semantic_digest"]),
            str(payload["assembly_digest"]),
            str(payload["program_result"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise IncrementalBuildError("malformed incremental artifact") from error
    if any(not value for value in (artifact.identity, artifact.output_digest, artifact.semantic_digest, artifact.assembly_digest)):
        raise IncrementalBuildError("incremental artifact contains an empty identity")
    expected_output = _digest({"semantic": artifact.semantic_digest, "assembly": artifact.assembly_digest, "result": artifact.program_result})
    if artifact.output_digest != expected_output:
        raise IncrementalBuildError("incremental artifact output digest mismatch")
    return artifact


def artifact_matches(artifact: IncrementalArtifact, graph: BuildGraph, provenance: IncrementalProvenance) -> bool:
    """Return HIT only for exact graph and provenance identity."""

    expected = _digest({"graph": graph.artifact_identity, "provenance": provenance.payload})
    return artifact.identity == expected and artifact.provenance == provenance


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
