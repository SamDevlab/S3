"""M2.86 explicit IR verifier canary contracts."""

from dataclasses import replace
from pathlib import Path

from bootstrap.s3.canonical_ir_candidate import (
    CanonicalIRBlock,
    CanonicalIRFunction,
    CanonicalIRInstruction,
    CanonicalIRProgram,
)
from bootstrap.s3.canonical_ir_verifier_candidate import IRVerificationResult
from bootstrap.s3.experiment_promotion import PromotionStatus
from bootstrap.s3.ir import IRType, IROpcode
from bootstrap.s3.ir_verifier_canary import M286_COMPONENT_ID, run_ir_canary


SOURCE = "a" * 40
ROOT = Path(__file__).parents[1]


def _program() -> CanonicalIRProgram:
    return CanonicalIRProgram(
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
    )


def test_canary_is_off_by_default_and_keeps_reference_output() -> None:
    result = run_ir_canary(_program(), source_lock_sha=SOURCE, observed_source_sha=SOURCE)
    assert result.decision.component_id == M286_COMPONENT_ID
    assert result.decision.status is PromotionStatus.OFF_BY_DEFAULT
    assert result.candidate_output is None
    assert result.selected_output == result.reference_output


def test_exact_opt_in_selects_matching_s3_verifier() -> None:
    result = run_ir_canary(
        _program(), source_lock_sha=SOURCE, observed_source_sha=SOURCE, explicit_opt_in=True
    )
    assert result.decision.status is PromotionStatus.CANDIDATE_SELECTED
    assert result.decision.selected
    assert result.reference_output == result.candidate_output
    assert result.differential is not None and result.differential.match


def test_source_lock_mismatch_falls_back_without_running_candidate() -> None:
    def unexpected(_program: CanonicalIRProgram) -> IRVerificationResult:
        raise AssertionError("candidate must not run on a source-lock mismatch")

    result = run_ir_canary(
        _program(),
        source_lock_sha=SOURCE,
        observed_source_sha="b" * 40,
        explicit_opt_in=True,
        candidate_runner=unexpected,
    )
    assert result.decision.status is PromotionStatus.FALLBACK
    assert result.decision.reason == "source_lock_mismatch"
    assert result.selected_output == result.reference_output


def test_candidate_error_is_visible_and_falls_back() -> None:
    def broken(_program: CanonicalIRProgram) -> IRVerificationResult:
        raise RuntimeError("verifier candidate failed")

    result = run_ir_canary(
        _program(),
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
    def drifted(program: CanonicalIRProgram) -> IRVerificationResult:
        reference = run_ir_canary(
            program, source_lock_sha=SOURCE, observed_source_sha=SOURCE
        ).reference_output
        assert reference is not None
        return replace(reference, diagnostic_code=reference.diagnostic_code + 1)

    result = run_ir_canary(
        _program(),
        source_lock_sha=SOURCE,
        observed_source_sha=SOURCE,
        explicit_opt_in=True,
        candidate_runner=drifted,
    )
    assert result.decision.status is PromotionStatus.FALLBACK
    assert result.decision.reason == "canonical_output_mismatch"
    assert result.selected_output == result.reference_output
