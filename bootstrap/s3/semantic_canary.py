"""M2.79 explicit-opt-in routing for the composed semantic candidate."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .control_flow_candidate import FlowStatement
from .differential import DifferentialCaseError, DifferentialHarness, DifferentialResult
from .experiment_promotion import (
    PromotionContract,
    PromotionDecision,
    PromotionStatus,
    resolve_promotion,
)
from .function_call_candidate import FunctionSignature
from .semantic_closure_candidate import (
    SemanticClosureInput,
    SemanticClosureResult,
    _reference_result,
    candidate_semantic_closure,
)


M279_COMPONENT_ID = "m2.78-semantic-closure"


class SemanticCanaryError(ValueError):
    """Raised when a semantic canary request cannot be represented safely."""


@dataclass(frozen=True, slots=True)
class SemanticCanaryResult:
    decision: PromotionDecision
    reference_output: SemanticClosureResult | None
    candidate_output: SemanticClosureResult | None
    differential: DifferentialResult | None

    @property
    def selected_output(self) -> SemanticClosureResult | None:
        if self.decision.selected:
            return self.candidate_output
        return self.reference_output

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision.to_dict(),
            "reference_output": (
                None
                if self.reference_output is None
                else {
                    "accepted": self.reference_output.accepted,
                    "identity": self.reference_output.identity,
                    "diagnostic_code": self.reference_output.diagnostic_code,
                }
            ),
            "candidate_output": (
                None
                if self.candidate_output is None
                else {
                    "accepted": self.candidate_output.accepted,
                    "identity": self.candidate_output.identity,
                    "diagnostic_code": self.candidate_output.diagnostic_code,
                }
            ),
            "differential": None if self.differential is None else self.differential.to_dict(),
        }


def semantic_closure_case_to_dict(case: SemanticClosureInput) -> dict[str, object]:
    """Encode one canonical case without computing any semantic answer."""

    if not isinstance(case, SemanticClosureInput):
        raise TypeError("case must be SemanticClosureInput")
    return {
        "symbol_entries": [list(entry) for entry in case.symbol_entries],
        "symbol_query": case.symbol_query,
        "name_entries": [list(entry) for entry in case.name_entries],
        "scope_parents": list(case.scope_parents),
        "name_query": case.name_query,
        "name_query_scope": case.name_query_scope,
        "scalar_operation": case.scalar_operation,
        "scalar_left_type": case.scalar_left_type,
        "scalar_right_type": case.scalar_right_type,
        "scalar_target_type": case.scalar_target_type,
        "place_operation": case.place_operation,
        "place_type": case.place_type,
        "place_kind": case.place_kind,
        "place_readable": case.place_readable,
        "place_writable": case.place_writable,
        "place_addressable": case.place_addressable,
        "place_initialized": case.place_initialized,
        "function_signatures": [
            {
                "function_id": signature.function_id,
                "parameter_types": list(signature.parameter_types),
                "return_type": signature.return_type,
            }
            for signature in case.function_signatures
        ],
        "function_query": case.function_query,
        "argument_types": list(case.argument_types),
        "record_types": list(case.record_types),
        "enum_variants": [list(variant) for variant in case.enum_variants],
        "flow_statements": [
            {
                "kind": statement.kind,
                "branch_left": statement.branch_left,
                "branch_right": statement.branch_right,
            }
            for statement in case.flow_statements
        ],
        "flow_requires_return": case.flow_requires_return,
    }


def semantic_closure_case_from_dict(value: Mapping[str, object]) -> SemanticClosureInput:
    """Decode the canonical mapping independently for reference and candidate."""

    if not isinstance(value, Mapping):
        raise TypeError("semantic closure input must be a mapping")
    signatures = tuple(
        FunctionSignature(
            int(item["function_id"]),
            tuple(int(type_id) for type_id in item["parameter_types"]),
            int(item["return_type"]),
        )
        for item in value["function_signatures"]  # type: ignore[index]
    )
    statements = tuple(
        FlowStatement(
            int(item["kind"]),
            int(item["branch_left"]),
            int(item["branch_right"]),
        )
        for item in value["flow_statements"]  # type: ignore[index]
    )
    return SemanticClosureInput(
        symbol_entries=tuple(tuple(int(part) for part in entry) for entry in value["symbol_entries"]),  # type: ignore[index]
        symbol_query=int(value["symbol_query"]),
        name_entries=tuple(tuple(int(part) for part in entry) for entry in value["name_entries"]),  # type: ignore[index]
        scope_parents=tuple(int(parent) for parent in value["scope_parents"]),  # type: ignore[index]
        name_query=int(value["name_query"]),
        name_query_scope=int(value["name_query_scope"]),
        scalar_operation=str(value["scalar_operation"]),
        scalar_left_type=int(value["scalar_left_type"]),
        scalar_right_type=int(value["scalar_right_type"]),
        scalar_target_type=int(value["scalar_target_type"]),
        place_operation=str(value["place_operation"]),
        place_type=int(value["place_type"]),
        place_kind=int(value["place_kind"]),
        place_readable=bool(value["place_readable"]),
        place_writable=bool(value["place_writable"]),
        place_addressable=bool(value["place_addressable"]),
        place_initialized=bool(value["place_initialized"]),
        function_signatures=signatures,
        function_query=int(value["function_query"]),
        argument_types=tuple(int(type_id) for type_id in value["argument_types"]),  # type: ignore[index]
        record_types=tuple(int(type_id) for type_id in value["record_types"]),  # type: ignore[index]
        enum_variants=tuple(
            tuple(int(type_id) for type_id in variant)
            for variant in value["enum_variants"]  # type: ignore[index]
        ),
        flow_statements=statements,
        flow_requires_return=bool(value["flow_requires_return"]),
    )


def _decode_output(payload: str | None) -> SemanticClosureResult | None:
    if payload is None:
        return None
    decoded = json.loads(payload)
    return SemanticClosureResult(
        bool(decoded["accepted"]),
        decoded["identity"],
        int(decoded["diagnostic_code"]),
    )


def _result_to_mapping(result: SemanticClosureResult) -> dict[str, object]:
    return {
        "accepted": result.accepted,
        "identity": result.identity,
        "diagnostic_code": result.diagnostic_code,
    }


def _fallback(
    reason: str,
    *,
    source_lock_match: bool,
) -> PromotionDecision:
    return PromotionDecision(
        M279_COMPONENT_ID,
        PromotionStatus.FALLBACK,
        False,
        True,
        source_lock_match,
        reason,
    )


def run_semantic_canary(
    case: SemanticClosureInput,
    *,
    source_lock_sha: str,
    observed_source_sha: str,
    explicit_opt_in: bool = False,
    candidate_runner: Callable[[SemanticClosureInput], SemanticClosureResult] | None = None,
) -> SemanticCanaryResult:
    """Route one composed case with explicit selection and visible fallback."""

    if not isinstance(case, SemanticClosureInput):
        raise TypeError("case must be SemanticClosureInput")
    candidate_runner = candidate_runner or candidate_semantic_closure
    reference_output = _reference_result(case)
    contract = PromotionContract(
        component_id=M279_COMPONENT_ID,
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
        return SemanticCanaryResult(decision, reference_output, None, None)

    input_value = semantic_closure_case_to_dict(case)
    provenance = {
        "component_id": M279_COMPONENT_ID,
        "source_lock_sha": source_lock_sha,
    }
    harness = DifferentialHarness()
    try:
        differential = harness.run(
            "m2.79-semantic-canary",
            input_value,
            lambda payload: _result_to_mapping(
                _reference_result(semantic_closure_case_from_dict(payload))
            ),
            lambda payload: _result_to_mapping(
                candidate_runner(semantic_closure_case_from_dict(payload))
            ),
            provenance=provenance,
        )
    except DifferentialCaseError:
        decision = _fallback("canonical_input_mismatch", source_lock_match=True)
        return SemanticCanaryResult(decision, reference_output, None, None)

    reference_observed = _decode_output(differential.reference_output)
    candidate_observed = _decode_output(differential.candidate_output)
    if differential.candidate_error is not None:
        decision = _fallback("candidate_error", source_lock_match=True)
    elif differential.reference_error is not None:
        decision = _fallback("reference_error", source_lock_match=True)
    elif not differential.match:
        decision = _fallback("canonical_output_mismatch", source_lock_match=True)
    else:
        contract = PromotionContract(
            component_id=M279_COMPONENT_ID,
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
    return SemanticCanaryResult(decision, reference_observed, candidate_observed, differential)
