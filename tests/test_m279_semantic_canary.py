"""M2.79 explicit-opt-in semantic candidate routing contracts."""

from dataclasses import replace

from bootstrap.s3.control_flow_candidate import FlowStatement, M277_RETURN
from bootstrap.s3.function_call_candidate import FunctionSignature
from bootstrap.s3.experiment_promotion import PromotionStatus
from bootstrap.s3.semantic_canary import (
    M279_COMPONENT_ID,
    run_semantic_canary,
)
from bootstrap.s3.semantic_closure_candidate import (
    SemanticClosureInput,
    SemanticClosureResult,
)


SOURCE = "a" * 40


def _case() -> SemanticClosureInput:
    return SemanticClosureInput(
        symbol_entries=((11, 1),),
        symbol_query=11,
        name_entries=((11, 1, 0),),
        scope_parents=(-1,),
        name_query=11,
        name_query_scope=0,
        scalar_operation="assign",
        scalar_left_type=1,
        scalar_target_type=1,
        function_signatures=(FunctionSignature(20, (1,), 2),),
        function_query=20,
        argument_types=(1,),
        record_types=(1, 2),
        enum_variants=((1,), (2, 3)),
        flow_statements=(FlowStatement(M277_RETURN),),
        flow_requires_return=True,
    )


def test_canary_is_off_by_default_and_exposes_reference_fallback() -> None:
    result = run_semantic_canary(
        _case(), source_lock_sha=SOURCE, observed_source_sha=SOURCE
    )
    assert result.decision.component_id == M279_COMPONENT_ID
    assert result.decision.status is PromotionStatus.OFF_BY_DEFAULT
    assert result.decision.selected is False
    assert result.decision.fallback_used is False
    assert result.candidate_output is None
    assert result.selected_output == result.reference_output


def test_exact_opt_in_selects_only_matching_candidate() -> None:
    result = run_semantic_canary(
        _case(), source_lock_sha=SOURCE, observed_source_sha=SOURCE, explicit_opt_in=True
    )
    assert result.decision.status is PromotionStatus.CANDIDATE_SELECTED
    assert result.decision.selected is True
    assert result.decision.fallback_used is False
    assert result.reference_output == result.candidate_output
    assert result.selected_output == result.candidate_output


def test_source_lock_mismatch_falls_back_without_running_candidate() -> None:
    result = run_semantic_canary(
        _case(), source_lock_sha=SOURCE, observed_source_sha="b" * 40, explicit_opt_in=True
    )
    assert result.decision.status is PromotionStatus.FALLBACK
    assert result.decision.reason == "source_lock_mismatch"
    assert result.candidate_output is None
    assert result.selected_output == result.reference_output


def test_candidate_error_is_visible_and_falls_back() -> None:
    def broken(_case: SemanticClosureInput) -> SemanticClosureResult:
        raise RuntimeError("candidate exploded")

    result = run_semantic_canary(
        _case(),
        source_lock_sha=SOURCE,
        observed_source_sha=SOURCE,
        explicit_opt_in=True,
        candidate_runner=broken,
    )
    assert result.decision.status is PromotionStatus.FALLBACK
    assert result.decision.reason == "candidate_error"
    assert result.decision.fallback_used is True
    assert result.selected_output == result.reference_output


def test_reference_candidate_drift_is_a_canonical_output_mismatch() -> None:
    def drifted(case: SemanticClosureInput) -> SemanticClosureResult:
        result = run_semantic_canary(
            case, source_lock_sha=SOURCE, observed_source_sha=SOURCE
        ).reference_output
        assert result is not None
        return replace(result, identity=(result.identity or 0) + 1)

    result = run_semantic_canary(
        _case(),
        source_lock_sha=SOURCE,
        observed_source_sha=SOURCE,
        explicit_opt_in=True,
        candidate_runner=drifted,
    )
    assert result.decision.status is PromotionStatus.FALLBACK
    assert result.decision.reason == "canonical_output_mismatch"
    assert result.selected_output == result.reference_output
