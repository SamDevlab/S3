"""M2.95 bounded compiler-driver composition over existing S3 contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .assembly_verification_closure import verify_assembly_reference
from .canonical_ir_candidate import CanonicalIRProgram, canonical_ir_identity
from .native_emission_boundary import (
    M293_TARGET_IDS,
    NativeEmissionPlan,
    prepare_native_emission_reference,
)
from .pipeline import run_source
from .lexer import SyntaxMode
from .source_workspace_boundary import WorkspaceBoundaryPlan


M295_STAGE_IDENTITY = 295
_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "driver" / "bounded_compiler_driver_candidate.s3"
).read_text(encoding="utf-8")


class BoundedCompilerDriverError(ValueError):
    """Raised when the bounded driver composition cannot be prepared."""


@dataclass(frozen=True, slots=True)
class BoundedCompilerPlan:
    workspace_plan: WorkspaceBoundaryPlan
    target: str
    ir_identity: int
    assembly_identity: int
    native_plan_identity: int
    assembly_text: str
    host_tool_required: bool
    native_artifact: None
    plan_identity: int


def _fold(values: tuple[int, ...]) -> int:
    return sum(values) % 301 % 181


def _validate_workspace_plan(plan: WorkspaceBoundaryPlan) -> None:
    if not isinstance(plan, WorkspaceBoundaryPlan):
        raise TypeError("workspace_plan must be WorkspaceBoundaryPlan")
    if not plan.host_service_required:
        raise BoundedCompilerDriverError("M2.95 requires the host workspace boundary")
    if not plan.ordered_paths or len(plan.ordered_paths) != len(plan.source_digests):
        raise BoundedCompilerDriverError("workspace plan metadata is incomplete")
    if not 0 <= plan.plan_identity < 181:
        raise BoundedCompilerDriverError("workspace plan identity is invalid")


def prepare_bounded_compiler_reference(
    workspace_plan: WorkspaceBoundaryPlan,
    program: CanonicalIRProgram,
    target: str,
) -> BoundedCompilerPlan:
    _validate_workspace_plan(workspace_plan)
    if target not in M293_TARGET_IDS:
        raise BoundedCompilerDriverError(f"unsupported native target: {target!r}")
    try:
        verification = verify_assembly_reference(program)
    except Exception as error:
        raise BoundedCompilerDriverError("emitted Assembly verification failed") from error
    try:
        native: NativeEmissionPlan = prepare_native_emission_reference(program, target)
    except Exception as error:
        raise BoundedCompilerDriverError("native target preparation failed") from error
    ir_identity = canonical_ir_identity(program)
    return BoundedCompilerPlan(
        workspace_plan=workspace_plan,
        target=target,
        ir_identity=ir_identity,
        assembly_identity=verification.verification_identity,
        native_plan_identity=native.plan_identity,
        assembly_text=native.assembly_text,
        host_tool_required=native.host_tool_required,
        native_artifact=native.native_artifact,
        plan_identity=_fold(
            (
                workspace_plan.plan_identity,
                ir_identity,
                verification.verification_identity,
                native.plan_identity,
                M295_STAGE_IDENTITY,
            )
        ),
    )


def _candidate(
    workspace_plan: WorkspaceBoundaryPlan,
    program: CanonicalIRProgram,
    target: str,
) -> BoundedCompilerPlan:
    reference = prepare_bounded_compiler_reference(workspace_plan, program, target)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    return compose_bounded_plan({reference.workspace_plan.plan_identity}, {reference.ir_identity}, {reference.assembly_identity}, {reference.native_plan_identity})\n"
    )
    try:
        identity = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise BoundedCompilerDriverError("S3 bounded compiler driver candidate failed") from error
    if not 0 <= identity < 181:
        raise BoundedCompilerDriverError("S3 bounded compiler driver returned invalid identity")
    return BoundedCompilerPlan(
        reference.workspace_plan,
        reference.target,
        reference.ir_identity,
        reference.assembly_identity,
        reference.native_plan_identity,
        reference.assembly_text,
        reference.host_tool_required,
        None,
        identity,
    )


def run_bounded_compiler_driver_differential(
    workspace_plan: WorkspaceBoundaryPlan,
    program: CanonicalIRProgram,
    target: str,
) -> tuple[BoundedCompilerPlan, BoundedCompilerPlan]:
    """Compare the host reference composition with the S3 candidate."""

    return prepare_bounded_compiler_reference(workspace_plan, program, target), _candidate(
        workspace_plan, program, target
    )
