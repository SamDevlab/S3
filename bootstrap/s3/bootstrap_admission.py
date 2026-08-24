"""M2.97 controlled admission boundary for a future bootstrap stage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .assembly import parse_assembly
from .assembly_verifier import AssemblyVerifier
from .driver_artifact_handoff import DriverArtifactHandoff
from .native_emission_boundary import M293_TARGET_IDS
from .lexer import SyntaxMode
from .pipeline import run_source


M297_STAGE_IDENTITY = 297
_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "bootstrap" / "bootstrap_admission_candidate.s3"
).read_text(encoding="utf-8")


class BootstrapAdmissionError(ValueError):
    """Raised when a driver artifact cannot enter a bootstrap stage."""


@dataclass(frozen=True, slots=True)
class BootstrapAdmission:
    artifact_format: str
    artifact_identity: int
    target: str
    assembly_identity: int
    bootstrap_allowed: bool
    host_tool_required: bool
    native_artifact: None
    admission_identity: int


def _fold(values: tuple[int, ...]) -> int:
    return sum(values) % 301 % 181


def admit_bootstrap_reference(
    artifact: DriverArtifactHandoff,
) -> BootstrapAdmission:
    if not isinstance(artifact, DriverArtifactHandoff):
        raise TypeError("artifact must be DriverArtifactHandoff")
    if artifact.format != "s3.driver-artifact.v1":
        raise BootstrapAdmissionError("unsupported driver artifact format")
    if not artifact.host_tool_required or artifact.native_artifact is not None:
        raise BootstrapAdmissionError("bootstrap admission requires an explicit host boundary")
    if artifact.target not in M293_TARGET_IDS:
        raise BootstrapAdmissionError("bootstrap target is unsupported")
    try:
        parsed = parse_assembly(artifact.assembly_text)
        AssemblyVerifier().validate(parsed, entry="f0")
    except Exception as error:
        raise BootstrapAdmissionError("bootstrap Assembly admission failed verification") from error
    return BootstrapAdmission(
        artifact_format=artifact.format,
        artifact_identity=artifact.artifact_identity,
        target=artifact.target,
        assembly_identity=artifact.assembly_identity,
        bootstrap_allowed=True,
        host_tool_required=True,
        native_artifact=None,
        admission_identity=_fold(
            (
                artifact.artifact_identity,
                artifact.assembly_identity,
                M293_TARGET_IDS[artifact.target],
                M297_STAGE_IDENTITY,
            )
        ),
    )


def _candidate(artifact: DriverArtifactHandoff) -> BootstrapAdmission:
    reference = admit_bootstrap_reference(artifact)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    return admit_bootstrap({reference.artifact_identity}, {reference.assembly_identity}, {M293_TARGET_IDS[reference.target]})\n"
    )
    try:
        identity = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise BootstrapAdmissionError("S3 bootstrap admission candidate failed") from error
    if not 0 <= identity < 181:
        raise BootstrapAdmissionError("S3 bootstrap admission returned invalid identity")
    return BootstrapAdmission(
        reference.artifact_format,
        reference.artifact_identity,
        reference.target,
        reference.assembly_identity,
        True,
        True,
        None,
        identity,
    )


def run_bootstrap_admission_differential(
    artifact: DriverArtifactHandoff,
) -> tuple[BootstrapAdmission, BootstrapAdmission]:
    """Compare controlled host admission with the S3 candidate."""

    return admit_bootstrap_reference(artifact), _candidate(artifact)
