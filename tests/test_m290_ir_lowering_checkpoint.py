"""M2.90 bounded IR/lowering checkpoint contracts."""

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
from bootstrap.s3.experiment_promotion import PromotionStatus
from bootstrap.s3.ir import IRType, IROpcode
from bootstrap.s3.ir_lowering_checkpoint import run_ir_lowering_checkpoint
from bootstrap.s3.lowering_checkpoint_candidate import LoweringCheckpointInput


SOURCE = "a" * 40


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


def test_checkpoint_keeps_both_reference_paths_by_default() -> None:
    result = run_ir_lowering_checkpoint(
        _case(), source_lock_sha=SOURCE, observed_source_sha=SOURCE
    )
    assert result.ir.decision.status is PromotionStatus.OFF_BY_DEFAULT
    assert result.lowering.decision.status is PromotionStatus.OFF_BY_DEFAULT
    assert not result.candidate_selected
    assert result.ir.selected_output == result.ir.reference_output
    assert result.lowering.selected_output == result.lowering.reference_output


def test_checkpoint_selects_both_candidates_only_with_exact_opt_in() -> None:
    result = run_ir_lowering_checkpoint(
        _case(),
        source_lock_sha=SOURCE,
        observed_source_sha=SOURCE,
        explicit_opt_in=True,
    )
    assert result.ir.decision.status is PromotionStatus.CANDIDATE_SELECTED
    assert result.lowering.decision.status is PromotionStatus.CANDIDATE_SELECTED
    assert result.candidate_selected
    assert result.ir.selected_output == result.ir.candidate_output
    assert result.lowering.selected_output == result.lowering.candidate_output


def test_checkpoint_source_lock_drift_falls_back_at_both_boundaries() -> None:
    result = run_ir_lowering_checkpoint(
        _case(),
        source_lock_sha=SOURCE,
        observed_source_sha="b" * 40,
        explicit_opt_in=True,
    )
    assert result.ir.decision.reason == "source_lock_mismatch"
    assert result.lowering.decision.reason == "source_lock_mismatch"
    assert not result.candidate_selected
    assert result.ir.selected_output == result.ir.reference_output
    assert result.lowering.selected_output == result.lowering.reference_output
