"""Bounded S3-authored workspace graph candidate with differential evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .differential import DifferentialHarness, DifferentialResult
from .lexer import SyntaxMode
from .pipeline import run_source


M266_MAX_MODULES = 8
M266_MAX_EDGES = 16
M266_MODULUS = 301
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2] / "selfhost" / "frontend" / "workspace_candidate.s3"
).read_text(encoding="utf-8")


class WorkspaceCandidateError(ValueError):
    """Raised when a bounded workspace graph is invalid."""


@dataclass(frozen=True, slots=True)
class WorkspaceCandidateEvidence:
    workspace: dict[str, list[str]]
    reference_fingerprint: int
    candidate_fingerprint: int
    differential: DifferentialResult

    @property
    def match(self) -> bool:
        return self.differential.match


def _symbol_hash(text: str) -> int:
    return sum(ord(char) for char in text) % M266_MODULUS


def _canonical_graph(workspace: dict[str, list[str]]) -> tuple[list[int], list[int], list[int]]:
    if not isinstance(workspace, dict) or not workspace:
        raise WorkspaceCandidateError("workspace must contain modules")
    if len(workspace) > M266_MAX_MODULES:
        raise WorkspaceCandidateError("workspace exceeds the M2.66 module bound")
    if any(not isinstance(name, str) or not name for name in workspace):
        raise WorkspaceCandidateError("workspace module names must be non-empty strings")
    names = sorted(workspace)
    module_ids = [_symbol_hash(name) for name in names]
    if len(set(module_ids)) != len(module_ids):
        raise WorkspaceCandidateError("workspace module hashes must be unique")
    edges: list[tuple[int, int]] = []
    known = set(names)
    for name in names:
        imports = workspace[name]
        if not isinstance(imports, list):
            raise WorkspaceCandidateError("workspace imports must be lists")
        for imported in imports:
            if imported not in known:
                raise WorkspaceCandidateError("workspace import target is unknown")
            edges.append((_symbol_hash(name), _symbol_hash(imported)))
    if len(edges) > M266_MAX_EDGES:
        raise WorkspaceCandidateError("workspace exceeds the M2.66 edge bound")
    edges.sort()
    return module_ids, [edge[0] for edge in edges], [edge[1] for edge in edges]


def _reference_fingerprint(workspace: dict[str, list[str]]) -> int:
    modules, edge_from, edge_to = _canonical_graph(workspace)
    checksum = 0
    for module_id in modules:
        checksum = (checksum * 32 + 100 + module_id) % M266_MODULUS
    for source, target in zip(edge_from, edge_to, strict=True):
        checksum = (checksum * 32 + 102 + source) % M266_MODULUS
        checksum = (checksum * 32 + 103 + target) % M266_MODULUS
    return checksum


def reference_workspace_fingerprint(workspace: dict[str, list[str]]) -> int:
    """Return a deterministic reference graph fingerprint."""

    return _reference_fingerprint(workspace)


def candidate_workspace_fingerprint(workspace: dict[str, list[str]]) -> int:
    """Run the S3 workspace graph candidate through the hosted emulator."""

    modules, edge_from, edge_to = _canonical_graph(workspace)
    module_text = [str(value) for value in modules]
    from_text = [str(value) for value in edge_from]
    to_text = [str(value) for value in edge_to]
    module_text.extend(["0"] * (M266_MAX_MODULES - len(module_text)))
    from_text.extend(["0"] * (M266_MAX_EDGES - len(from_text)))
    to_text.extend(["0"] * (M266_MAX_EDGES - len(to_text)))
    main_source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    module_ids: tryte[{M266_MAX_MODULES}] = [{', '.join(module_text)}]\n"
        + f"    edge_from: tryte[{M266_MAX_EDGES}] = [{', '.join(from_text)}]\n"
        + f"    edge_to: tryte[{M266_MAX_EDGES}] = [{', '.join(to_text)}]\n"
        + f"    return workspace_graph_fingerprint(module_ids, edge_from, edge_to, {len(modules)}, {len(edge_from)})\n"
    )
    try:
        result = run_source(main_source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise WorkspaceCandidateError("S3 workspace candidate execution failed") from error
    if result < 0:
        raise WorkspaceCandidateError("S3 workspace candidate rejected the graph")
    return result


def run_workspace_differential(
    workspace: dict[str, list[str]],
    *,
    provenance: dict[str, object] | None = None,
) -> WorkspaceCandidateEvidence:
    """Compare canonical Python workspace graph evidence with S3."""

    candidate = candidate_workspace_fingerprint(workspace)
    reference = reference_workspace_fingerprint(workspace)
    result = DifferentialHarness(max_bytes=4096).run(
        "m2.66-workspace-candidate",
        {"workspace": workspace},
        lambda value: {"fingerprint": reference_workspace_fingerprint(value["workspace"])},
        lambda value: {"fingerprint": candidate_workspace_fingerprint(value["workspace"])},
        provenance=provenance
        or {
            "component_id": "m2.66-workspace-candidate",
            "source": "selfhost/frontend/workspace_candidate.s3",
        },
    )
    return WorkspaceCandidateEvidence(workspace, reference, candidate, result)
