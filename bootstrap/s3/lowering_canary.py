"""M2.89 explicit-opt-in routing for the composed lowering closure."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from .composed_lowering_closure_candidate import (
    ComposedLoweringResult,
    compose_lowering_reference,
    run_composed_lowering_differential,
)
from .differential import DifferentialCaseError, DifferentialHarness, DifferentialResult
from .experiment_promotion import (
    PromotionContract,
    PromotionDecision,
    PromotionStatus,
    resolve_promotion,
)
from .lowering_checkpoint_candidate import LoweringCheckpointInput, LoweringCheckpointResult


M289_COMPONENT_ID = "m2.89-lowering-canary"


@dataclass(frozen=True, slots=True)
class LoweringCanaryResult:
    decision: PromotionDecision
    reference_output: ComposedLoweringResult | None
    candidate_output: ComposedLoweringResult | None
    differential: DifferentialResult | None

    @property
    def selected_output(self) -> ComposedLoweringResult | None:
        if self.decision.selected:
            return self.candidate_output
        return self.reference_output


def _result_to_mapping(result: ComposedLoweringResult) -> dict[str, object]:
    checkpoint = result.checkpoint
    return {
        "expression_identity": checkpoint.expression_identity,
        "call_identity": checkpoint.call_identity,
        "verifier_accepted": checkpoint.verifier_accepted,
        "verifier_code": checkpoint.verifier_code,
        "checkpoint_identity": checkpoint.checkpoint_identity,
        "composed_identity": result.composed_identity,
    }


def _decode_output(payload: str | None) -> ComposedLoweringResult | None:
    if payload is None:
        return None
    decoded = json.loads(payload)
    checkpoint = LoweringCheckpointResult(
        expression_identity=int(decoded["expression_identity"]),
        call_identity=int(decoded["call_identity"]),
        verifier_accepted=bool(decoded["verifier_accepted"]),
        verifier_code=int(decoded["verifier_code"]),
        checkpoint_identity=int(decoded["checkpoint_identity"]),
    )
    return ComposedLoweringResult(checkpoint, int(decoded["composed_identity"]))


def _fallback(reason: str, *, source_lock_match: bool) -> PromotionDecision:
    return PromotionDecision(
        M289_COMPONENT_ID,
        PromotionStatus.FALLBACK,
        False,
        True,
        source_lock_match,
        reason,
    )


def run_lowering_canary(
    value: LoweringCheckpointInput,
    *,
    source_lock_sha: str,
    observed_source_sha: str,
    explicit_opt_in: bool = False,
    candidate_runner: Callable[[LoweringCheckpointInput], ComposedLoweringResult] | None = None,
) -> LoweringCanaryResult:
    """Select composed lowering only after exact source and differential gates."""

    reference_output = compose_lowering_reference(value)
    contract = PromotionContract(
        component_id=M289_COMPONENT_ID,
        source_lock_sha=source_lock_sha,
        eligible=True,
        correctness_evidence="PASS" if explicit_opt_in else "NOT_RUN",
        structural_evidence="PASS",
        fallback_available=True,
        default_enabled=False,
    )
    decision = resolve_promotion(
        contract,
        observed_source_sha=observed_source_sha,
        explicit_opt_in=explicit_opt_in,
    )
    if not explicit_opt_in or decision.status is PromotionStatus.FALLBACK:
        return LoweringCanaryResult(decision, reference_output, None, None)

    candidate_runner = candidate_runner or (lambda item: run_composed_lowering_differential(item)[1])
    harness = DifferentialHarness(max_bytes=8192)
    try:
        differential = harness.run(
            M289_COMPONENT_ID,
            {"checkpoint_identity": reference_output.checkpoint.checkpoint_identity},
            lambda _payload: _result_to_mapping(reference_output),
            lambda _payload: _result_to_mapping(candidate_runner(value)),
            provenance={
                "component_id": M289_COMPONENT_ID,
                "source_lock_sha": source_lock_sha,
                "candidate": "selfhost/lowering/composed_lowering_closure_candidate.s3",
            },
        )
    except DifferentialCaseError:
        return LoweringCanaryResult(
            _fallback("canonical_input_mismatch", source_lock_match=True),
            reference_output,
            None,
            None,
        )

    observed_reference = _decode_output(differential.reference_output)
    observed_candidate = _decode_output(differential.candidate_output)
    if differential.candidate_error is not None:
        decision = _fallback("candidate_error", source_lock_match=True)
    elif differential.reference_error is not None:
        decision = _fallback("reference_error", source_lock_match=True)
    elif not differential.match:
        decision = _fallback("canonical_output_mismatch", source_lock_match=True)
    else:
        contract = PromotionContract(
            component_id=M289_COMPONENT_ID,
            source_lock_sha=source_lock_sha,
            eligible=True,
            correctness_evidence="PASS",
            structural_evidence="PASS",
            fallback_available=True,
            default_enabled=False,
        )
        decision = resolve_promotion(
            contract,
            observed_source_sha=observed_source_sha,
            explicit_opt_in=True,
        )
    return LoweringCanaryResult(decision, observed_reference, observed_candidate, differential)
