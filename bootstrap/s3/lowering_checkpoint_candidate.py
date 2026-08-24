"""M2.87 bounded checkpoint for expression/call lowering plus IR verification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .call_aggregate_lowering_candidate import (
    CallLoweringInput,
    call_plan_identity,
    lower_call_reference,
)
from .canonical_ir_candidate import CanonicalIRProgram, canonical_ir_identity
from .canonical_ir_verifier_candidate import verify_ir_reference
from .expression_lowering_candidate import (
    ExpressionProgram,
    lower_expression_reference,
)
from .lexer import SyntaxMode
from .pipeline import run_source


M287_STAGE_IDENTITY = 207
_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "lowering" / "lowering_checkpoint_candidate.s3"
).read_text(encoding="utf-8")


class LoweringCheckpointError(ValueError):
    """Raised when the bounded lowering checkpoint cannot run safely."""


@dataclass(frozen=True, slots=True)
class LoweringCheckpointInput:
    expression: ExpressionProgram
    call: CallLoweringInput
    ir: CanonicalIRProgram


@dataclass(frozen=True, slots=True)
class LoweringCheckpointResult:
    expression_identity: int
    call_identity: int
    verifier_accepted: bool
    verifier_code: int
    checkpoint_identity: int


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


def lower_checkpoint_reference(value: LoweringCheckpointInput) -> LoweringCheckpointResult:
    expression = lower_expression_reference(value.expression)
    call = lower_call_reference(value.call)
    verifier = verify_ir_reference(value.ir)
    expression_identity = canonical_ir_identity(expression)
    call_identity = call_plan_identity(call)
    checkpoint_identity = _fold(
        (
            expression_identity,
            call_identity,
            1 if verifier.accepted else -1,
            verifier.diagnostic_code,
        )
    )
    return LoweringCheckpointResult(
        expression_identity,
        call_identity,
        verifier.accepted,
        verifier.diagnostic_code,
        checkpoint_identity,
    )


def _candidate(value: LoweringCheckpointInput) -> LoweringCheckpointResult:
    reference = lower_checkpoint_reference(value)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + "    return lowering_checkpoint("
        + f"{reference.expression_identity}, {reference.call_identity}, "
        + f"{1 if reference.verifier_accepted else -1}, {reference.verifier_code})\n"
    )
    try:
        checkpoint_identity = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise LoweringCheckpointError("S3 lowering checkpoint candidate failed") from error
    if not 0 <= checkpoint_identity < 181:
        raise LoweringCheckpointError("S3 lowering checkpoint returned invalid identity")
    return LoweringCheckpointResult(
        reference.expression_identity,
        reference.call_identity,
        reference.verifier_accepted,
        reference.verifier_code,
        checkpoint_identity,
    )


def run_lowering_checkpoint_differential(
    value: LoweringCheckpointInput,
) -> tuple[LoweringCheckpointResult, LoweringCheckpointResult]:
    return lower_checkpoint_reference(value), _candidate(value)
