"""M2.98 deterministic reproducibility seal for bootstrap admission."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .bootstrap_admission import BootstrapAdmission
from .native_emission_boundary import M293_TARGET_IDS
from .lexer import SyntaxMode
from .pipeline import run_source


M298_STAGE_IDENTITY = 298
_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "bootstrap" / "bootstrap_reproducibility_candidate.s3"
).read_text(encoding="utf-8")


class BootstrapReproducibilityError(ValueError):
    """Raised when a bootstrap admission cannot receive a reproducibility seal."""


@dataclass(frozen=True, slots=True)
class BootstrapReproducibilitySeal:
    admission_identity: int
    first_identity: int
    second_identity: int
    reproducible: bool
    host_tool_required: bool
    native_artifact: None
    seal_identity: int


def _fold(values: tuple[int, ...]) -> int:
    return sum(values) % 301 % 181


def _validate_admission(admission: BootstrapAdmission) -> None:
    if not isinstance(admission, BootstrapAdmission):
        raise TypeError("admission must be BootstrapAdmission")
    if not admission.bootstrap_allowed:
        raise BootstrapReproducibilityError("bootstrap admission is not allowed")
    if not admission.host_tool_required or admission.native_artifact is not None:
        raise BootstrapReproducibilityError("bootstrap admission has invalid native boundary")
    if admission.target not in M293_TARGET_IDS:
        raise BootstrapReproducibilityError("bootstrap target is unsupported")


def seal_bootstrap_reference(
    admission: BootstrapAdmission,
) -> BootstrapReproducibilitySeal:
    _validate_admission(admission)
    first = _fold(
        (
            admission.artifact_identity,
            admission.assembly_identity,
            M293_TARGET_IDS[admission.target],
            admission.admission_identity,
        )
    )
    second = _fold(
        (
            admission.artifact_identity,
            admission.assembly_identity,
            M293_TARGET_IDS[admission.target],
            admission.admission_identity,
        )
    )
    return BootstrapReproducibilitySeal(
        admission_identity=admission.admission_identity,
        first_identity=first,
        second_identity=second,
        reproducible=first == second,
        host_tool_required=True,
        native_artifact=None,
        seal_identity=_fold((admission.admission_identity, first, second, M298_STAGE_IDENTITY)),
    )


def _candidate(admission: BootstrapAdmission) -> BootstrapReproducibilitySeal:
    reference = seal_bootstrap_reference(admission)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    return seal_bootstrap({admission.artifact_identity}, {admission.assembly_identity}, {reference.admission_identity}, {M293_TARGET_IDS[admission.target]})\n"
    )
    try:
        identity = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise BootstrapReproducibilityError("S3 bootstrap reproducibility candidate failed") from error
    if not 0 <= identity < 181:
        raise BootstrapReproducibilityError("S3 bootstrap reproducibility returned invalid identity")
    return BootstrapReproducibilitySeal(
        reference.admission_identity,
        reference.first_identity,
        reference.second_identity,
        True,
        True,
        None,
        identity,
    )


def run_bootstrap_reproducibility_differential(
    admission: BootstrapAdmission,
) -> tuple[BootstrapReproducibilitySeal, BootstrapReproducibilitySeal]:
    """Compare deterministic reference materialization with the S3 candidate."""

    return seal_bootstrap_reference(admission), _candidate(admission)
