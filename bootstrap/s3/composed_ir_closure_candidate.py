"""M2.85 composition of the bounded expression and call producers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .canonical_ir_candidate import canonical_ir_identity
from .call_aggregate_lowering_candidate import (
    CallLoweringInput,
    _candidate_identity as _candidate_call_identity,
    call_plan_identity,
    lower_call_reference,
)
from .expression_lowering_candidate import (
    ExpressionProgram,
    _candidate_identity as _candidate_expression_identity,
    lower_expression_reference,
)
from .lexer import SyntaxMode
from .pipeline import run_source


M285_STAGE_IDENTITY = 201
_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "ir" / "composed_ir_closure_candidate.s3"
).read_text(encoding="utf-8")


class ComposedIRClosureError(ValueError):
    """Raised when M2.85 cannot compose bounded producer outputs."""


@dataclass(frozen=True, slots=True)
class ComposedIRInput:
    expression: ExpressionProgram
    call: CallLoweringInput


@dataclass(frozen=True, slots=True)
class ComposedIRResult:
    expression_identity: int
    call_identity: int
    composed_identity: int


@dataclass(frozen=True, slots=True)
class ComposedIREvidence:
    reference: ComposedIRResult
    candidate: ComposedIRResult

    @property
    def match(self) -> bool:
        return self.reference == self.candidate


def _fold(values: tuple[int, ...]) -> int:
    result = 0
    for value in values:
        result += value
        while result > 364:
            result -= 729
        while result < -364:
            result += 729
        while result < 0:
            result += 181
        while result > 180:
            result -= 181
    return result


def compose_ir_reference(value: ComposedIRInput) -> ComposedIRResult:
    expression = lower_expression_reference(value.expression)
    call = lower_call_reference(value.call)
    expression_identity = canonical_ir_identity(expression)
    call_identity = call_plan_identity(call)
    return ComposedIRResult(expression_identity, call_identity, _fold((expression_identity, call_identity, 285)))


def _candidate(value: ComposedIRInput) -> ComposedIRResult:
    reference = compose_ir_reference(value)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    return compose_ir({reference.expression_identity}, {reference.call_identity})\n"
    )
    try:
        composed = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise ComposedIRClosureError("S3 composed IR candidate failed") from error
    if not 0 <= composed < 181:
        raise ComposedIRClosureError("S3 composed IR candidate returned invalid identity")
    return ComposedIRResult(reference.expression_identity, reference.call_identity, composed)


def run_composed_ir_differential(value: ComposedIRInput) -> ComposedIREvidence:
    return ComposedIREvidence(compose_ir_reference(value), _candidate(value))
