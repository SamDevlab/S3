"""M2.94 source/workspace boundary with deterministic host-provided metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .lexer import SyntaxMode
from .pipeline import run_source


M294_MAX_UNITS = 8
M294_STAGE_IDENTITY = 294
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "selfhost"
    / "driver"
    / "source_workspace_boundary_candidate.s3"
).read_text(encoding="utf-8")


class SourceWorkspaceBoundaryError(ValueError):
    """Raised when host-provided source/workspace metadata is invalid."""


def _canonical_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise SourceWorkspaceBoundaryError("source path must be non-empty")
    if "\\" in value or value.startswith("/"):
        raise SourceWorkspaceBoundaryError("source path must be relative POSIX text")
    path = PurePosixPath(value)
    if path == PurePosixPath(".") or ".." in path.parts or "." in path.parts:
        raise SourceWorkspaceBoundaryError("source path contains an invalid component")
    canonical = path.as_posix()
    if canonical != value or not canonical:
        raise SourceWorkspaceBoundaryError("source path is not canonical")
    return canonical


def _digest_identity(value: str) -> int:
    result = 0
    for char in value:
        result = (result * 16 + int(char, 16)) % 181
    return result


def _path_identity(value: str) -> int:
    return sum(ord(char) for char in value) % 181


@dataclass(frozen=True, slots=True)
class SourceUnit:
    path: str
    source_sha256: str

    def __post_init__(self) -> None:
        _canonical_path(self.path)
        if _SHA256.fullmatch(self.source_sha256) is None:
            raise SourceWorkspaceBoundaryError("source_sha256 must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class WorkspaceLoadRequest:
    units: tuple[SourceUnit, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.units, tuple) or not self.units:
            raise SourceWorkspaceBoundaryError("workspace requires source units")
        if len(self.units) > M294_MAX_UNITS:
            raise SourceWorkspaceBoundaryError("workspace exceeds the M2.94 unit bound")
        paths = tuple(unit.path for unit in self.units)
        if len(set(paths)) != len(paths):
            raise SourceWorkspaceBoundaryError("workspace source paths must be unique")


@dataclass(frozen=True, slots=True)
class WorkspaceBoundaryPlan:
    ordered_paths: tuple[str, ...]
    source_digests: tuple[str, ...]
    host_service_required: bool
    plan_identity: int


def _add_mod(left: int, right: int) -> int:
    value = left + right
    return value % 301


def _fold_identity(value: int) -> int:
    return value % 181


def _canonical_units(request: WorkspaceLoadRequest) -> tuple[SourceUnit, ...]:
    return tuple(sorted(request.units, key=lambda unit: unit.path))


def _identity(request: WorkspaceLoadRequest) -> int:
    units = _canonical_units(request)
    checksum = 0
    for index, unit in enumerate(units, start=1):
        checksum = _add_mod(checksum, _path_identity(unit.path))
        checksum = _add_mod(checksum, _digest_identity(unit.source_sha256))
        checksum = _add_mod(checksum, len(unit.path))
        checksum = _add_mod(checksum, index)
    return _fold_identity(_add_mod(checksum, M294_STAGE_IDENTITY))


def prepare_workspace_reference(request: WorkspaceLoadRequest) -> WorkspaceBoundaryPlan:
    units = _canonical_units(request)
    if any(len(unit.path) > 180 for unit in units):
        raise SourceWorkspaceBoundaryError("source path exceeds the M2.94 path bound")
    return WorkspaceBoundaryPlan(
        ordered_paths=tuple(unit.path for unit in units),
        source_digests=tuple(unit.source_sha256 for unit in units),
        host_service_required=True,
        plan_identity=_identity(request),
    )


def _candidate(request: WorkspaceLoadRequest) -> WorkspaceBoundaryPlan:
    reference = prepare_workspace_reference(request)
    units = _canonical_units(request)
    path_ids = [_path_identity(unit.path) for unit in units]
    digest_ids = [_digest_identity(unit.source_sha256) for unit in units]
    path_lengths = [len(unit.path) for unit in units]
    padding = M294_MAX_UNITS - len(units)
    path_ids.extend([0] * padding)
    digest_ids.extend([0] * padding)
    path_lengths.extend([0] * padding)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    path_ids: tryte[{M294_MAX_UNITS}] = [{', '.join(map(str, path_ids))}]\n"
        + f"    digest_ids: tryte[{M294_MAX_UNITS}] = [{', '.join(map(str, digest_ids))}]\n"
        + f"    path_lengths: tryte[{M294_MAX_UNITS}] = [{', '.join(map(str, path_lengths))}]\n"
        + f"    return prepare_workspace_plan(path_ids, digest_ids, path_lengths, {len(units)})\n"
    )
    try:
        identity = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise SourceWorkspaceBoundaryError("S3 source/workspace candidate execution failed") from error
    if not 0 <= identity < 181:
        raise SourceWorkspaceBoundaryError("S3 source/workspace candidate returned invalid identity")
    return WorkspaceBoundaryPlan(
        reference.ordered_paths,
        reference.source_digests,
        True,
        identity,
    )


def run_source_workspace_differential(
    request: WorkspaceLoadRequest,
) -> tuple[WorkspaceBoundaryPlan, WorkspaceBoundaryPlan]:
    """Compare host-validated reference metadata with the S3 candidate."""

    return prepare_workspace_reference(request), _candidate(request)
