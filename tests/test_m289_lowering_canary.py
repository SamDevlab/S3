"""M2.89 explicit lowering canary contracts."""

from dataclasses import replace

from bootstrap.s3.call_aggregate_lowering_candidate import CallLoweringInput
from bootstrap.s3.canonical_ir_candidate import (
    CanonicalIRBlock,
    CanonicalIRFunction,
    CanonicalIRInstruction,
    CanonicalIRProgram,
)
from bootstrap.s3.composed_lowering_closure_candidate import ComposedLoweringResult
from bootstrap.s3.experiment_promotion import PromotionStatus
from bootstrap.s3.expression_lowering_candidate import (
    ExpressionNode,
    ExpressionProgram,
    M282_ADD,
    M282_LITERAL,
)
from bootstrap.s3.ir import IRType, IROpcode
from bootstrap.s3.lowering_canary import M289_COMPONENT_ID, run_lowering_canary
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


def test_canary_is_off_by_default_and_keeps_reference() -> None:
    result = run_lowering_canary(_case(), source_lock_sha=SOURCE, observed_source_sha=SOURCE)
    assert result.decision.component_id == M289_COMPONENT_ID
    assert result.decision.status is PromotionStatus.OFF_BY_DEFAULT
    assert result.candidate_output is None
    assert result.selected_output == result.reference_output


def test_exact_opt_in_selects_matching_composed_lowering() -> None:
    result = run_lowering_canary(
        _case(), source_lock_sha=SOURCE, observed_source_sha=SOURCE, explicit_opt_in=True
    )
    assert result.decision.status is PromotionStatus.CANDIDATE_SELECTED
    assert result.decision.selected
    assert result.reference_output == result.candidate_output
    assert result.differential is not None and result.differential.match


def test_source_lock_mismatch_falls_back_before_candidate_execution() -> None:
    def unexpected(_value: LoweringCheckpointInput) -> ComposedLoweringResult:
        raise AssertionError("candidate must not run after source-lock drift")

    result = run_lowering_canary(
        _case(),
        source_lock_sha=SOURCE,
        observed_source_sha="b" * 40,
        explicit_opt_in=True,
        candidate_runner=unexpected,
    )
    assert result.decision.status is PromotionStatus.FALLBACK
    assert result.decision.reason == "source_lock_mismatch"


def test_candidate_error_is_visible_and_falls_back() -> None:
    def broken(_value: LoweringCheckpointInput) -> ComposedLoweringResult:
        raise RuntimeError("composed lowering failed")

    result = run_lowering_canary(
        _case(),
        source_lock_sha=SOURCE,
        observed_source_sha=SOURCE,
        explicit_opt_in=True,
        candidate_runner=broken,
    )
    assert result.decision.status is PromotionStatus.FALLBACK
    assert result.decision.reason == "candidate_error"
    assert result.decision.fallback_used
    assert result.selected_output == result.reference_output


def test_candidate_drift_is_a_canonical_output_mismatch() -> None:
    def drifted(value: LoweringCheckpointInput) -> ComposedLoweringResult:
        reference = run_lowering_canary(
            value, source_lock_sha=SOURCE, observed_source_sha=SOURCE
        ).reference_output
        assert reference is not None
        return replace(reference, composed_identity=reference.composed_identity + 1)

    result = run_lowering_canary(
        _case(),
        source_lock_sha=SOURCE,
        observed_source_sha=SOURCE,
        explicit_opt_in=True,
        candidate_runner=drifted,
    )
    assert result.decision.status is PromotionStatus.FALLBACK
    assert result.decision.reason == "canonical_output_mismatch"
    assert result.selected_output == result.reference_output
