"""M2.86 explicit-opt-in routing for the S3-authored IR verifier."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .canonical_ir_candidate import (
    CanonicalIRBlock,
    CanonicalIRFunction,
    CanonicalIRInstruction,
    CanonicalIRProgram,
    canonical_ir_to_dict,
)
from .canonical_ir_verifier_candidate import (
    IRVerificationResult,
    verify_ir_candidate,
    verify_ir_reference,
)
from .differential import DifferentialCaseError, DifferentialHarness, DifferentialResult
from .experiment_promotion import (
    PromotionContract,
    PromotionDecision,
    PromotionStatus,
    resolve_promotion,
)
from .ir import IRType, IROpcode


M286_COMPONENT_ID = "m2.86-ir-verifier-canary"


class IRCanaryError(ValueError):
    """Raised when an IR canary request cannot be represented safely."""


@dataclass(frozen=True, slots=True)
class IRCanaryResult:
    decision: PromotionDecision
    reference_output: IRVerificationResult | None
    candidate_output: IRVerificationResult | None
    differential: DifferentialResult | None

    @property
    def selected_output(self) -> IRVerificationResult | None:
        if self.decision.selected:
            return self.candidate_output
        return self.reference_output


def _program_from_dict(value: Mapping[str, object]) -> CanonicalIRProgram:
    try:
        functions = []
        for function in value["functions"]:  # type: ignore[index]
            blocks = []
            for block in function["blocks"]:  # type: ignore[index]
                instructions = tuple(
                    CanonicalIRInstruction(
                        opcode=IROpcode(item["opcode"]),
                        result=item["result"],
                        operands=tuple(item["operands"]),
                        immediate=item["immediate"],
                        targets=tuple(item["targets"]),
                    )
                    for item in block["instructions"]
                )
                blocks.append(
                    CanonicalIRBlock(
                        name_id=block["name_id"],
                        instructions=instructions,
                    )
                )
            functions.append(
                CanonicalIRFunction(
                    name_id=function["name_id"],
                    return_type=IRType(function["return_type"]),
                    register_types=tuple(IRType(item) for item in function["register_types"]),
                    blocks=tuple(blocks),
                )
            )
        return CanonicalIRProgram(functions=tuple(functions))
    except (KeyError, TypeError, ValueError) as error:
        raise IRCanaryError("canonical IR input cannot be decoded") from error


def _result_to_mapping(result: IRVerificationResult) -> dict[str, object]:
    return {
        "accepted": result.accepted,
        "diagnostic_code": result.diagnostic_code,
    }


def _decode_output(payload: str | None) -> IRVerificationResult | None:
    if payload is None:
        return None
    decoded = json.loads(payload)
    return IRVerificationResult(
        accepted=bool(decoded["accepted"]),
        diagnostic_code=int(decoded["diagnostic_code"]),
    )


def _fallback(reason: str, *, source_lock_match: bool) -> PromotionDecision:
    return PromotionDecision(
        M286_COMPONENT_ID,
        PromotionStatus.FALLBACK,
        False,
        True,
        source_lock_match,
        reason,
    )


def run_ir_canary(
    program: CanonicalIRProgram,
    *,
    source_lock_sha: str,
    observed_source_sha: str,
    explicit_opt_in: bool = False,
    candidate_runner: Callable[[CanonicalIRProgram], IRVerificationResult] | None = None,
) -> IRCanaryResult:
    """Select the verifier candidate only after an exact differential pass."""

    reference_output = verify_ir_reference(program)
    contract = PromotionContract(
        component_id=M286_COMPONENT_ID,
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
        return IRCanaryResult(decision, reference_output, None, None)

    candidate_runner = candidate_runner or verify_ir_candidate
    input_value = canonical_ir_to_dict(program)
    harness = DifferentialHarness(max_bytes=8192)
    try:
        differential = harness.run(
            M286_COMPONENT_ID,
            input_value,
            lambda payload: _result_to_mapping(
                verify_ir_reference(_program_from_dict(payload))  # type: ignore[arg-type]
            ),
            lambda payload: _result_to_mapping(
                candidate_runner(_program_from_dict(payload))  # type: ignore[arg-type]
            ),
            provenance={
                "component_id": M286_COMPONENT_ID,
                "source_lock_sha": source_lock_sha,
                "candidate": "selfhost/verifier/canonical_ir_verifier_candidate.s3",
            },
        )
    except DifferentialCaseError:
        return IRCanaryResult(
            _fallback("canonical_input_mismatch", source_lock_match=True),
            reference_output,
            None,
            None,
        )

    candidate_output = _decode_output(differential.candidate_output)
    observed_reference = _decode_output(differential.reference_output)
    if differential.candidate_error is not None:
        decision = _fallback("candidate_error", source_lock_match=True)
    elif differential.reference_error is not None:
        decision = _fallback("reference_error", source_lock_match=True)
    elif not differential.match:
        decision = _fallback("canonical_output_mismatch", source_lock_match=True)
    else:
        contract = PromotionContract(
            component_id=M286_COMPONENT_ID,
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
    return IRCanaryResult(decision, observed_reference, candidate_output, differential)
