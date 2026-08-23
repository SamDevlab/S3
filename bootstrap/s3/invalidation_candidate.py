"""Bounded S3-authored incremental invalidation candidate with differential evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .differential import DifferentialHarness, DifferentialResult
from .lexer import SyntaxMode
from .pipeline import run_source
from .workspace_candidate import (
    M266_MAX_EDGES,
    M266_MAX_MODULES,
    M266_MODULUS,
    WorkspaceCandidateError,
    _canonical_graph,
    _symbol_hash,
)


M267_MAX_MODULES = M266_MAX_MODULES
M267_MAX_EDGES = M266_MAX_EDGES
M267_MODULUS = M266_MODULUS
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "selfhost"
    / "frontend"
    / "invalidation_candidate.s3"
).read_text(encoding="utf-8")


class InvalidationCandidateError(ValueError):
    """Raised when a bounded invalidation graph or change set is invalid."""


@dataclass(frozen=True, slots=True)
class InvalidationCandidateEvidence:
    workspace: dict[str, list[str]]
    changed: tuple[str, ...]
    reference_fingerprint: int
    candidate_fingerprint: int
    differential: DifferentialResult

    @property
    def match(self) -> bool:
        return self.differential.match


def _canonical_inputs(
    workspace: dict[str, list[str]], changed: list[str]
) -> tuple[list[int], list[int], list[int], list[int]]:
    if not isinstance(changed, list) or not changed:
        raise InvalidationCandidateError("changed modules must be non-empty")
    if len(changed) > M267_MAX_MODULES:
        raise InvalidationCandidateError("changed modules exceed the M2.67 bound")
    if any(not isinstance(name, str) or not name for name in changed):
        raise InvalidationCandidateError("changed module names must be non-empty strings")
    if len(set(changed)) != len(changed):
        raise InvalidationCandidateError("changed modules must be unique")
    try:
        modules, edge_from, edge_to = _canonical_graph(workspace)
    except WorkspaceCandidateError as error:
        raise InvalidationCandidateError(str(error)) from error
    known = set(workspace)
    if any(name not in known for name in changed):
        raise InvalidationCandidateError("changed module is unknown")
    changed_ids = sorted(_symbol_hash(name) for name in changed)
    return modules, edge_from, edge_to, changed_ids


def _reference_fingerprint(workspace: dict[str, list[str]], changed: list[str]) -> int:
    modules, edge_from, edge_to, changed_ids = _canonical_inputs(workspace, changed)
    invalidated = set(changed_ids)
    changed_flag = True
    while changed_flag:
        changed_flag = False
        for source, target in zip(edge_from, edge_to, strict=True):
            if target in invalidated and source not in invalidated:
                invalidated.add(source)
                changed_flag = True
    checksum = 0
    for module_id in modules:
        if module_id in invalidated:
            for _ in range(5):
                checksum = (checksum * 2) % M267_MODULUS
            checksum = (checksum + 110 + module_id) % M267_MODULUS
    return checksum


def reference_invalidation_fingerprint(
    workspace: dict[str, list[str]], changed: list[str]
) -> int:
    """Return the deterministic reference invalidation fingerprint."""

    return _reference_fingerprint(workspace, changed)


def candidate_invalidation_fingerprint(
    workspace: dict[str, list[str]], changed: list[str]
) -> int:
    """Run the S3 incremental invalidation candidate through the emulator."""

    modules, edge_from, edge_to, changed_ids = _canonical_inputs(workspace, changed)
    module_text = [str(value) for value in modules]
    from_text = [str(value) for value in edge_from]
    to_text = [str(value) for value in edge_to]
    changed_text = [str(value) for value in changed_ids]
    module_text.extend(["0"] * (M267_MAX_MODULES - len(module_text)))
    from_text.extend(["0"] * (M267_MAX_EDGES - len(from_text)))
    to_text.extend(["0"] * (M267_MAX_EDGES - len(to_text)))
    changed_text.extend(["0"] * (M267_MAX_MODULES - len(changed_text)))
    main_source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    module_ids: tryte[{M267_MAX_MODULES}] = [{', '.join(module_text)}]\n"
        + f"    edge_from: tryte[{M267_MAX_EDGES}] = [{', '.join(from_text)}]\n"
        + f"    edge_to: tryte[{M267_MAX_EDGES}] = [{', '.join(to_text)}]\n"
        + f"    changed_ids: tryte[{M267_MAX_MODULES}] = [{', '.join(changed_text)}]\n"
        + f"    return incremental_invalidation_fingerprint(module_ids, edge_from, edge_to, changed_ids, {len(modules)}, {len(edge_from)}, {len(changed_ids)})\n"
    )
    try:
        result = run_source(main_source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise InvalidationCandidateError("S3 invalidation candidate execution failed") from error
    if result < 0:
        raise InvalidationCandidateError("S3 invalidation candidate rejected the graph")
    return result


def run_invalidation_differential(
    workspace: dict[str, list[str]],
    changed: list[str],
    *,
    provenance: dict[str, object] | None = None,
) -> InvalidationCandidateEvidence:
    """Compare Python invalidation closure evidence with the S3 candidate."""

    candidate = candidate_invalidation_fingerprint(workspace, changed)
    reference = reference_invalidation_fingerprint(workspace, changed)
    result = DifferentialHarness(max_bytes=4096).run(
        "m2.67-incremental-invalidation-candidate",
        {"workspace": workspace, "changed": changed},
        lambda value: {
            "fingerprint": reference_invalidation_fingerprint(
                value["workspace"], value["changed"]
            )
        },
        lambda value: {
            "fingerprint": candidate_invalidation_fingerprint(
                value["workspace"], value["changed"]
            )
        },
        provenance=provenance
        or {
            "component_id": "m2.67-incremental-invalidation-candidate",
            "source": "selfhost/frontend/invalidation_candidate.s3",
        },
    )
    return InvalidationCandidateEvidence(
        workspace,
        tuple(changed),
        reference,
        candidate,
        result,
    )
