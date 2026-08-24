"""M2.88 composed lowering closure contracts."""

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
from bootstrap.s3.lowering_checkpoint_candidate import LoweringCheckpointInput
from bootstrap.s3.composed_lowering_closure_candidate import (
    run_composed_lowering_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (
    ROOT / "selfhost" / "lowering" / "composed_lowering_closure_candidate.s3"
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


def test_candidate_source_has_one_composition_entrypoint_and_no_main() -> None:
    assert "fn compose_lowering" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_composed_lowering_matches_the_checkpoint() -> None:
    reference, candidate = run_composed_lowering_differential(_case())
    assert reference == candidate
    assert reference.checkpoint.verifier_accepted


def test_composed_identity_changes_when_checkpoint_changes() -> None:
    first, _ = run_composed_lowering_differential(_case())
    changed = _case()
    changed = LoweringCheckpointInput(
        expression=ExpressionProgram(
            nodes=(ExpressionNode(M282_LITERAL, value=5),),
            root=0,
        ),
        call=changed.call,
        ir=changed.ir,
    )
    second, _ = run_composed_lowering_differential(changed)
    assert first.composed_identity != second.composed_identity
