"""M2.93 explicit host-tool boundary for native emission preparation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .assembly_verification_closure import verify_assembly_reference
from .canonical_ir_candidate import CanonicalIRProgram
from .lexer import SyntaxMode
from .pipeline import run_source


M293_TARGET_IDS = {"x86_64": 1, "aarch64": 2, "macos_arm64": 3}
M293_STAGE_IDENTITY = 293
_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "native" / "native_emission_boundary_candidate.s3"
).read_text(encoding="utf-8")


class NativeEmissionBoundaryError(ValueError):
    """Raised when native emission preparation is outside the contract."""


@dataclass(frozen=True, slots=True)
class NativeEmissionPlan:
    target: str
    assembly_text: str
    assembly_identity: int
    host_tool_required: bool
    native_artifact: None
    plan_identity: int


def _add_mod(left: int, right: int) -> int:
    value = left + right
    while value > 364:
        value -= 729
    while value < -364:
        value += 729
    return value


def _fold(values: tuple[int, ...]) -> int:
    result = 0
    for value in values:
        result = _add_mod(result, value)
        while result < 0:
            result += 181
        while result > 180:
            result -= 181
    return result


def prepare_native_emission_reference(
    program: CanonicalIRProgram,
    target: str,
) -> NativeEmissionPlan:
    if target not in M293_TARGET_IDS:
        raise NativeEmissionBoundaryError(f"unsupported native target: {target!r}")
    verification = verify_assembly_reference(program)
    target_id = M293_TARGET_IDS[target]
    return NativeEmissionPlan(
        target=target,
        assembly_text=verification.emission.text,
        assembly_identity=verification.verification_identity,
        host_tool_required=True,
        native_artifact=None,
        plan_identity=_fold((verification.verification_identity, target_id, M293_STAGE_IDENTITY)),
    )


def _candidate(program: CanonicalIRProgram, target: str) -> NativeEmissionPlan:
    reference = prepare_native_emission_reference(program, target)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    return prepare_native_plan({reference.assembly_identity}, {M293_TARGET_IDS[target]})\n"
    )
    try:
        identity = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise NativeEmissionBoundaryError("S3 native emission boundary candidate failed") from error
    if not 0 <= identity < 181:
        raise NativeEmissionBoundaryError("S3 native emission boundary returned invalid identity")
    return NativeEmissionPlan(
        reference.target,
        reference.assembly_text,
        reference.assembly_identity,
        True,
        None,
        identity,
    )


def run_native_emission_boundary_differential(
    program: CanonicalIRProgram,
    target: str,
) -> tuple[NativeEmissionPlan, NativeEmissionPlan]:
    return prepare_native_emission_reference(program, target), _candidate(program, target)
