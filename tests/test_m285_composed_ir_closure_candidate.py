"""M2.85 composed IR closure contracts."""

from pathlib import Path

from bootstrap.s3.call_aggregate_lowering_candidate import CallLoweringInput
from bootstrap.s3.composed_ir_closure_candidate import (
    ComposedIRInput,
    run_composed_ir_differential,
)
from bootstrap.s3.expression_lowering_candidate import (
    ExpressionNode,
    ExpressionProgram,
    M282_ADD,
    M282_LITERAL,
)
from bootstrap.s3.ir import IRType


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost" / "ir" / "composed_ir_closure_candidate.s3").read_text(encoding="utf-8")


def _case() -> ComposedIRInput:
    return ComposedIRInput(
        expression=ExpressionProgram(
            nodes=(ExpressionNode(M282_LITERAL, value=4), ExpressionNode(M282_LITERAL, value=2), ExpressionNode(M282_ADD, left=0, right=1)),
            root=2,
        ),
        call=CallLoweringInput(
            callee_id=17,
            argument_types=(IRType.TRYTE, IRType.I64),
            argument_registers=(0, 1),
            result_types=(IRType.I64, IRType.F64),
        ),
    )


def test_candidate_source_has_one_composition_entrypoint_and_no_main() -> None:
    assert "fn compose_ir" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_composed_expression_and_call_identity_match() -> None:
    evidence = run_composed_ir_differential(_case())
    assert evidence.match
    assert evidence.reference.expression_identity == evidence.candidate.expression_identity
    assert evidence.reference.call_identity == evidence.candidate.call_identity


def test_composed_identity_changes_when_call_shape_changes() -> None:
    first = run_composed_ir_differential(_case())
    changed = _case()
    changed = ComposedIRInput(changed.expression, CallLoweringInput(17, changed.call.argument_types, changed.call.argument_registers, (IRType.I64, IRType.F64, IRType.TRYTE)))
    second = run_composed_ir_differential(changed)
    assert first.reference.composed_identity != second.reference.composed_identity
