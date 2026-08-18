"""Bounded self-hosting gate for the normalized S3 test-manifest contract.

The TOML reader remains the authoritative Python implementation.  This module
only sends a small, normalized scalar projection to an S3 candidate so the
candidate can be checked without giving it file-system access or making the
M1.60 gate depend on an unfinished hosted standard library.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .test_runner import S3TestManifest
from .pipeline import compile_source, run_source


M160_PROFILE = "m160-bounded-manifest-projection-v1"
M160_MAX_SOURCE_BYTES = 2048
M160_MAX_FRAMES = 8
M160_MAX_INSTRUCTIONS = 256
M160_MAX_MEMORY_CELLS = 4096

_OPTIMIZATION_CODES = {"O0": 0, "O1": 1, "O2": 2}
_MODE_CODES = {"hosted": 0, "native": 1, "both": 2}


class SelfHostingGateError(ValueError):
    """Raised when the bounded candidate violates the gate contract."""


@dataclass(frozen=True, slots=True)
class ManifestProjection:
    seed: int
    timeout_ms: int
    max_frames: int
    max_instructions: int
    optimization_code: int
    mode_code: int
    case_count: int
    source_count: int
    expected_sum: int

    def __post_init__(self) -> None:
        values = (
            self.seed,
            self.timeout_ms,
            self.max_frames,
            self.max_instructions,
            self.optimization_code,
            self.mode_code,
            self.case_count,
            self.source_count,
            self.expected_sum,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise SelfHostingGateError("manifest projection fields must be integers")
        if any(value < 0 for value in values):
            raise SelfHostingGateError("manifest projection fields must be non-negative")
        if self.optimization_code not in set(_OPTIMIZATION_CODES.values()):
            raise SelfHostingGateError("unsupported optimization projection")
        if self.mode_code not in set(_MODE_CODES.values()):
            raise SelfHostingGateError("unsupported mode projection")
        if self.case_count < 1 or self.source_count < 1:
            raise SelfHostingGateError("manifest projection must contain test sources")


@dataclass(frozen=True, slots=True)
class SelfHostingGateResult:
    profile: str
    oracle_value: int
    candidate_value: int | None
    equal: bool
    deterministic: bool
    used_fallback: bool
    fallback_reason: str | None
    source_bytes: int
    memory_cells: int
    max_frames: int
    max_instructions: int
    projection: ManifestProjection

    def as_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "oracle_value": self.oracle_value,
            "candidate_value": self.candidate_value,
            "equal": self.equal,
            "deterministic": self.deterministic,
            "used_fallback": self.used_fallback,
            "fallback_reason": self.fallback_reason,
            "source_bytes": self.source_bytes,
            "memory_cells": self.memory_cells,
            "max_frames": self.max_frames,
            "max_instructions": self.max_instructions,
            "projection": asdict(self.projection),
        }


def projection_from_manifest(manifest: S3TestManifest) -> ManifestProjection:
    """Normalize the public manifest model into the bounded candidate input."""

    try:
        optimization_code = _OPTIMIZATION_CODES[manifest.optimization]
        mode_code = _MODE_CODES[manifest.mode]
    except KeyError as error:
        raise SelfHostingGateError("manifest contains an unknown normalized field") from error
    return ManifestProjection(
        seed=manifest.seed,
        timeout_ms=manifest.timeout_ms,
        max_frames=manifest.max_frames,
        max_instructions=manifest.max_instructions,
        optimization_code=optimization_code,
        mode_code=mode_code,
        case_count=len(manifest.tests),
        source_count=sum(len(case.sources) for case in manifest.tests),
        expected_sum=sum(case.expected for case in manifest.tests),
    )


def manifest_projection_oracle(projection: ManifestProjection) -> int:
    """Return the Python-authoritative deterministic projection checksum."""

    fields = (
        projection.seed,
        projection.timeout_ms,
        projection.max_frames,
        projection.max_instructions,
        projection.optimization_code,
        projection.mode_code,
        projection.case_count,
        projection.source_count,
        projection.expected_sum,
    )
    return sum((index + 1) * value for index, value in enumerate(fields))


def _candidate_source(projection: ManifestProjection) -> str:
    values = ", ".join(
        str(value)
        for value in (
            projection.seed,
            projection.timeout_ms,
            projection.max_frames,
            projection.max_instructions,
            projection.optimization_code,
            projection.mode_code,
            projection.case_count,
            projection.source_count,
            projection.expected_sum,
        )
    )
    return f"""\
fn weighted_projection(
    seed: i64,
    timeout_ms: i64,
    max_frames: i64,
    max_instructions: i64,
    optimization_code: i64,
    mode_code: i64,
    case_count: i64,
    source_count: i64,
    expected_sum: i64
) -> i64:
    return seed + timeout_ms * 2 + max_frames * 3 + max_instructions * 4 + optimization_code * 5 + mode_code * 6 + case_count * 7 + source_count * 8 + expected_sum * 9

fn main() -> i64:
    return weighted_projection({values})
"""


def _run_candidate(source: str) -> tuple[int, int, int]:
    source_bytes = len(source.encode("utf-8"))
    if source_bytes > M160_MAX_SOURCE_BYTES:
        raise SelfHostingGateError("candidate source exceeds the M1.60 byte budget")
    compilation = compile_source(source, "O0")
    main = next(function for function in compilation.assembly.functions if function.name == "main")
    memory_cells = sum(memory.length for memory in main.memory_objects)
    if memory_cells > M160_MAX_MEMORY_CELLS:
        raise SelfHostingGateError("candidate exceeds the M1.60 memory budget")
    value = run_source(
        source,
        optimization="O0",
        max_frames=M160_MAX_FRAMES,
        max_instructions=M160_MAX_INSTRUCTIONS,
    )
    return value, source_bytes, memory_cells


def run_manifest_self_hosting_gate(
    path: str | Path,
    *,
    allow_fallback: bool = True,
    candidate_source: str | None = None,
) -> SelfHostingGateResult:
    """Compare the bounded S3 projection with Python, with fail-closed fallback."""

    manifest = S3TestManifest.load(path)
    projection = projection_from_manifest(manifest)
    oracle_value = manifest_projection_oracle(projection)
    source = candidate_source or _candidate_source(projection)
    try:
        first, source_bytes, memory_cells = _run_candidate(source)
        second, second_source_bytes, second_memory_cells = _run_candidate(source)
        if (source_bytes, memory_cells) != (second_source_bytes, second_memory_cells):
            raise SelfHostingGateError("candidate resource accounting is not deterministic")
        if first != second:
            raise SelfHostingGateError("candidate result is not deterministic")
        if first != oracle_value:
            raise SelfHostingGateError(
                f"candidate disagrees with Python oracle: {first} != {oracle_value}"
            )
        return SelfHostingGateResult(
            M160_PROFILE,
            oracle_value,
            first,
            True,
            True,
            False,
            None,
            source_bytes,
            memory_cells,
            M160_MAX_FRAMES,
            M160_MAX_INSTRUCTIONS,
            projection,
        )
    except SelfHostingGateError:
        raise
    except Exception as error:
        if not allow_fallback:
            raise SelfHostingGateError("bounded candidate failed without fallback") from error
        return SelfHostingGateResult(
            M160_PROFILE,
            oracle_value,
            None,
            True,
            True,
            True,
            f"{type(error).__name__}: {error}",
            0,
            0,
            M160_MAX_FRAMES,
            M160_MAX_INSTRUCTIONS,
            projection,
        )
