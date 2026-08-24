"""M2.87 expression/call lowering and verifier checkpoint contracts."""

from dataclasses import replace
from pathlib import Path

from bootstrap.s3.call_aggregate_lowering_candidate import CallLoweringInput
from bootstrap.s3.canonical_ir_candidate import (
    CanonicalIRBlock,
    CanonicalIRFunction,
    CanonicalIRInstruction,
    CanonicalIRProgram,
)
from bootstrap.s3.expression_lowering_candidate import (
    ExpressionNode,
    ExpressionProgram,
    M282_ADD,
    M282_LITERAL,
)
from bootstrap.s3.ir import IRType, IROpcode
from bootstrap.s3.lowering_checkpoint_candidate import (
    LoweringCheckpointInput,
    run_lowering_checkpoint_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (
    ROOT / "selfhost" / "lowering" / "lowering_checkpoint_candidate.s3"
).read_text(encoding="utf-8")


def _case() -> LoweringCheckpointInput:
    return LoweringCheckpointInput(
        expression=ExpressionProgram(
            nodes=(
                ExpressionNode(M282_LITERAL, value=4),
                ExpressionNode(M282_LITERAL, value=2),
                ExpressionNode(M282_ADD, left=0, right=1),
            ),
            root=2,
        ),
        call=CallLoweringInput(
            callee_id=17,
            argument_types=(IRType.TRYTE, IRType.I64),
            argument_registers=(0, 1),
            result_types=(IRType.I64, IRType.F64),
        ),
        ir=CanonicalIRProgram(
            functions=(
                CanonicalIRFunction(
                    name_id=0,
                    return_type=IRType.TRYTE,
                    register_types=(IRType.TRYTE, IRType.TRYTE),
                    blocks=(
                        CanonicalIRBlock(
                            name_id=0,
                            instructions=(
                                CanonicalIRInstruction(IROpcode.CONST, result=0, immediate=1),
                                CanonicalIRInstruction(IROpcode.ADD, result=1, operands=(0, 0)),
                                CanonicalIRInstruction(IROpcode.RETURN, operands=(1,)),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def test_candidate_source_has_one_checkpoint_entrypoint_and_no_main() -> None:
    assert "fn lowering_checkpoint" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_lowering_checkpoint_matches_all_three_upstream_contracts() -> None:
    reference, candidate = run_lowering_checkpoint_differential(_case())
    assert reference == candidate
    assert reference.verifier_accepted


def test_invalid_ir_remains_visible_at_the_checkpoint() -> None:
    case = _case()
    block = case.ir.functions[0].blocks[0]
    invalid = replace(
        case.ir,
        functions=(
            replace(
                case.ir.functions[0],
                blocks=(replace(block, instructions=block.instructions[:2]),),
            ),
        ),
    )
    changed = replace(case, ir=invalid)
    reference, candidate = run_lowering_checkpoint_differential(changed)
    assert reference == candidate
    assert not reference.verifier_accepted
    assert reference.verifier_code == 205


def test_expression_shape_changes_checkpoint_identity() -> None:
    first, _ = run_lowering_checkpoint_differential(_case())
    changed = _case()
    changed = replace(
        changed,
        expression=ExpressionProgram(
            nodes=(ExpressionNode(M282_LITERAL, value=5),),
            root=0,
        ),
    )
    second, _ = run_lowering_checkpoint_differential(changed)
    assert first.expression_identity != second.expression_identity
    assert first.checkpoint_identity != second.checkpoint_identity
