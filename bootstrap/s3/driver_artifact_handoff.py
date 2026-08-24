"""M2.96 deterministic handoff for the bounded compiler driver artifact."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .assembly import parse_assembly
from .assembly_verifier import AssemblyVerifier
from .bounded_compiler_driver import BoundedCompilerPlan
from .native_emission_boundary import M293_TARGET_IDS
from .lexer import SyntaxMode
from .pipeline import run_source


M296_STAGE_IDENTITY = 296
_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "driver" / "driver_artifact_handoff_candidate.s3"
).read_text(encoding="utf-8")


class DriverArtifactHandoffError(ValueError):
    """Raised when a driver plan cannot cross the artifact handoff."""


@dataclass(frozen=True, slots=True)
class DriverArtifactHandoff:
    format: str
    workspace_identity: int
    driver_plan_identity: int
    target: str
    assembly_text: str
    assembly_identity: int
    host_tool_required: bool
    native_artifact: None
    artifact_identity: int


def _fold(values: tuple[int, ...]) -> int:
    return sum(values) % 301 % 181


def prepare_driver_artifact_reference(
    plan: BoundedCompilerPlan,
) -> DriverArtifactHandoff:
    if not isinstance(plan, BoundedCompilerPlan):
        raise TypeError("plan must be BoundedCompilerPlan")
    if not plan.host_tool_required or plan.native_artifact is not None:
        raise DriverArtifactHandoffError("driver plan has invalid native boundary")
    if plan.target not in M293_TARGET_IDS:
        raise DriverArtifactHandoffError("driver plan target is unsupported")
    try:
        parsed = parse_assembly(plan.assembly_text)
        AssemblyVerifier().validate(parsed, entry="f0")
    except Exception as error:
        raise DriverArtifactHandoffError("driver Assembly handoff failed verification") from error
    return DriverArtifactHandoff(
        format="s3.driver-artifact.v1",
        workspace_identity=plan.workspace_plan.plan_identity,
        driver_plan_identity=plan.plan_identity,
        target=plan.target,
        assembly_text=plan.assembly_text,
        assembly_identity=plan.assembly_identity,
        host_tool_required=True,
        native_artifact=None,
        artifact_identity=_fold(
            (
                plan.workspace_plan.plan_identity,
                plan.plan_identity,
                plan.assembly_identity,
                M293_TARGET_IDS[plan.target],
                M296_STAGE_IDENTITY,
            )
        ),
    )


def _candidate(plan: BoundedCompilerPlan) -> DriverArtifactHandoff:
    reference = prepare_driver_artifact_reference(plan)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    return compose_driver_handoff({reference.workspace_identity}, {reference.driver_plan_identity}, {reference.assembly_identity}, {M293_TARGET_IDS[reference.target]})\n"
    )
    try:
        identity = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise DriverArtifactHandoffError("S3 driver artifact handoff candidate failed") from error
    if not 0 <= identity < 181:
        raise DriverArtifactHandoffError("S3 driver artifact handoff returned invalid identity")
    return DriverArtifactHandoff(
        reference.format,
        reference.workspace_identity,
        reference.driver_plan_identity,
        reference.target,
        reference.assembly_text,
        reference.assembly_identity,
        True,
        None,
        identity,
    )


def run_driver_artifact_handoff_differential(
    plan: BoundedCompilerPlan,
) -> tuple[DriverArtifactHandoff, DriverArtifactHandoff]:
    """Compare the verified host handoff with the S3 candidate."""

    return prepare_driver_artifact_reference(plan), _candidate(plan)
