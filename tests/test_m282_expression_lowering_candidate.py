"""M2.82 expression lowering contracts."""

from pathlib import Path

import pytest

from bootstrap.s3.expression_lowering_candidate import (
    ExpressionLoweringError,
    ExpressionNode,
    ExpressionProgram,
    M282_ADD,
    M282_DIFFERENCE,
    M282_LITERAL,
    M282_MULTIPLY,
    lower_expression_reference,
    run_expression_lowering_differential,
)
from bootstrap.s3.ir import IROpcode


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (
    ROOT / "selfhost" / "lowering" / "expression_lowering_candidate.s3"
).read_text(encoding="utf-8")


def _program(kind: str = M282_ADD) -> ExpressionProgram:
    return ExpressionProgram(
        nodes=(
            ExpressionNode(M282_LITERAL, value=4),
            ExpressionNode(M282_LITERAL, value=2),
            ExpressionNode(kind, left=0, right=1),
        ),
        root=2,
    )


def test_candidate_source_has_one_lowering_entrypoint_and_no_main() -> None:
    assert "fn lower_expression" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE
    assert "tryte[3]" in SELFHOST_SOURCE


@pytest.mark.parametrize(
    ("kind", "opcode"),
    [
        (M282_ADD, IROpcode.ADD),
        (M282_DIFFERENCE, IROpcode.NUMERIC_DIFFERENCE),
        (M282_MULTIPLY, IROpcode.MULTIPLY),
    ],
)
def test_reference_lowering_emits_canonical_expression_instruction(
    kind: str,
    opcode: IROpcode,
) -> None:
    program = lower_expression_reference(_program(kind))
    instructions = program.functions[0].blocks[0].instructions
    assert instructions[2].opcode is opcode
    assert instructions[2].result == 2
    assert instructions[2].operands == (0, 1)
    assert instructions[3].opcode is IROpcode.RETURN
    assert instructions[3].operands == (2,)


def test_reference_and_s3_lowering_match_exactly() -> None:
    evidence = run_expression_lowering_differential(_program())
    assert evidence.match
    assert evidence.candidate_identity is not None


def test_lowering_rejects_forward_child_before_candidate_execution() -> None:
    invalid = ExpressionProgram(
        nodes=(
            ExpressionNode(M282_ADD, left=1, right=0),
            ExpressionNode(M282_LITERAL, value=1),
        ),
        root=0,
    )
    with pytest.raises(ExpressionLoweringError, match="earlier node"):
        run_expression_lowering_differential(invalid)
