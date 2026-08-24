"""M2.92 verification closure for the bounded emitted Assembly subset."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .assembly import parse_assembly
from .assembly_emission_candidate import (
    AssemblyEmissionResult,
    emit_assembly_reference,
)
from .assembly_verifier import AssemblyVerifier
from .canonical_ir_candidate import CanonicalIRProgram
from .lexer import SyntaxMode
from .pipeline import run_source


M292_STAGE_IDENTITY = 292
_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "assembly" / "assembly_verification_closure.s3"
).read_text(encoding="utf-8")


class AssemblyVerificationClosureError(ValueError):
    """Raised when emitted Assembly cannot pass the M2.92 boundary."""


@dataclass(frozen=True, slots=True)
class AssemblyVerificationResult:
    emission: AssemblyEmissionResult
    verified: bool
    verification_identity: int


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


def verify_assembly_reference(program: CanonicalIRProgram) -> AssemblyVerificationResult:
    try:
        emission = emit_assembly_reference(program)
        parsed = parse_assembly(emission.text)
        AssemblyVerifier().validate(parsed, entry="f0")
    except Exception as error:
        raise AssemblyVerificationClosureError("emitted Assembly failed verification") from error
    return AssemblyVerificationResult(
        emission=emission,
        verified=True,
        verification_identity=_fold((emission.identity, 1, M292_STAGE_IDENTITY)),
    )


def _candidate(program: CanonicalIRProgram) -> AssemblyVerificationResult:
    reference = verify_assembly_reference(program)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    return verify_emitted_assembly({reference.emission.identity}, 1)\n"
    )
    try:
        identity = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise AssemblyVerificationClosureError("S3 Assembly verification candidate failed") from error
    if not 0 <= identity < 181:
        raise AssemblyVerificationClosureError("S3 Assembly verification returned invalid identity")
    return AssemblyVerificationResult(reference.emission, True, identity)


def run_assembly_verification_differential(
    program: CanonicalIRProgram,
) -> tuple[AssemblyVerificationResult, AssemblyVerificationResult]:
    return verify_assembly_reference(program), _candidate(program)
