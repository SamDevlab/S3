"""M2.99 promotion-readiness decision without production promotion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .bootstrap_reproducibility import BootstrapReproducibilitySeal
from .native_emission_boundary import M293_TARGET_IDS
from .lexer import SyntaxMode
from .pipeline import run_source


M299_STAGE_IDENTITY = 299
_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "bootstrap" / "bootstrap_promotion_readiness_candidate.s3"
).read_text(encoding="utf-8")


class BootstrapPromotionReadinessError(ValueError):
    """Raised when a reproducibility seal cannot enter the readiness gate."""


@dataclass(frozen=True, slots=True)
class BootstrapPromotionReadiness:
    seal_identity: int
    admission_identity: int
    target: str
    candidate_ready: bool
    production_promotion: bool
    full_self_hosting_claim: bool
    decision_identity: int


def _fold(values: tuple[int, ...]) -> int:
    return sum(values) % 301 % 181


def assess_promotion_readiness_reference(
    seal: BootstrapReproducibilitySeal,
    target: str,
) -> BootstrapPromotionReadiness:
    if not isinstance(seal, BootstrapReproducibilitySeal):
        raise TypeError("seal must be BootstrapReproducibilitySeal")
    if not seal.reproducible or seal.first_identity != seal.second_identity:
        raise BootstrapPromotionReadinessError("bootstrap reproducibility seal is not valid")
    if not seal.host_tool_required or seal.native_artifact is not None:
        raise BootstrapPromotionReadinessError("readiness requires an explicit host boundary")
    if target not in M293_TARGET_IDS:
        raise BootstrapPromotionReadinessError("promotion target is unsupported")
    return BootstrapPromotionReadiness(
        seal_identity=seal.seal_identity,
        admission_identity=seal.admission_identity,
        target=target,
        candidate_ready=True,
        production_promotion=False,
        full_self_hosting_claim=False,
        decision_identity=_fold(
            (
                seal.seal_identity,
                seal.admission_identity,
                M293_TARGET_IDS[target],
                M299_STAGE_IDENTITY,
            )
        ),
    )


def _candidate(
    seal: BootstrapReproducibilitySeal,
    target: str,
) -> BootstrapPromotionReadiness:
    reference = assess_promotion_readiness_reference(seal, target)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    return assess_promotion_readiness({reference.seal_identity}, {reference.admission_identity}, {M293_TARGET_IDS[target]})\n"
    )
    try:
        identity = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise BootstrapPromotionReadinessError("S3 promotion readiness candidate failed") from error
    if not 0 <= identity < 181:
        raise BootstrapPromotionReadinessError("S3 promotion readiness returned invalid identity")
    return BootstrapPromotionReadiness(
        reference.seal_identity,
        reference.admission_identity,
        reference.target,
        True,
        False,
        False,
        identity,
    )


def run_bootstrap_promotion_readiness_differential(
    seal: BootstrapReproducibilitySeal,
    target: str,
) -> tuple[BootstrapPromotionReadiness, BootstrapPromotionReadiness]:
    """Compare readiness policy with the S3 candidate."""

    return assess_promotion_readiness_reference(seal, target), _candidate(seal, target)
