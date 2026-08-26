from __future__ import annotations

import pytest

from tools.bind_stage1_semantic_ir_native_calls import (
    SemanticIRCallBoundaryError,
    bind_reports,
)


pytestmark = pytest.mark.s3_fast


def _contract() -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-semantic-ir-native-call-boundary-contract.v1",
        "semantic_ir_schema": "s3.selfhost.stage1-final-semantic-ir-verifier.v1",
        "native_call_schema": "s3.selfhost.stage1-native-call-reconciliation.v1",
        "output_schema": "s3.selfhost.stage1-final-semantic-ir-verifier.v1",
        "authority": {"output_authority": "STAGE1_FINAL_SEMANTIC_IR_NATIVE_CALL_BOUND"},
    }


def _semantic() -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-final-semantic-ir-verifier.v1",
        "canonical_source": {"sha256": "a" * 64, "bytes": 100},
        "stage1": {"sha256": "b" * 64, "bytes": 200},
        "inventory_counts": {"calls": 5, "call_arguments": 9},
        "qualification": {
            "semantic_ir": "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET",
            "verifier_v2": "PASS",
            "general_emitter": "PASS_BOOTSTRAP_REQUIRED_OPCODES",
            "stage2_allowed_from_this_report_alone": False,
            "full_self_hosting": False,
        },
        "evidence_inputs": {},
    }


def _calls() -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-native-call-reconciliation.v1",
        "status": "PASS_NATIVE_CURRENT_SOURCE_CALL_RECONCILIATION",
        "native_evidence": True,
        "canonical_source": {"sha256": "a" * 64, "bytes": 100},
        "stage1": {"sha256": "b" * 64, "bytes": 200},
        "native": {"audit": {"ir_call_count": 5, "ir_call_arg_pool_count": 9}},
        "qualification": {
            "native_call_capacity": "PASS",
            "native_call_argument_capacity": "PASS",
            "semantic_call_linkage_complete_from_this_report_alone": False,
        },
    }


def test_matching_semantic_and_native_call_counts_bind() -> None:
    result = bind_reports(_semantic(), _calls(), contract=_contract())
    assert result["authority"] == "STAGE1_FINAL_SEMANTIC_IR_NATIVE_CALL_BOUND"
    assert result["native_call_capacity_dependency"]["semantic_calls_equal_native_high_water"] is True
    assert result["native_call_capacity_dependency"]["semantic_call_arguments_equal_native_high_water"] is True
    assert result["qualification"]["native_call_capacity_boundary"] == "PASS"
    assert result["qualification"]["stage2_allowed_from_this_report_alone"] is False


def test_semantic_call_count_mismatch_blocks() -> None:
    semantic = _semantic()
    semantic["inventory_counts"]["calls"] = 4
    with pytest.raises(SemanticIRCallBoundaryError, match="calls disagree"):
        bind_reports(semantic, _calls(), contract=_contract())


def test_semantic_argument_count_mismatch_blocks() -> None:
    semantic = _semantic()
    semantic["inventory_counts"]["call_arguments"] = 8
    with pytest.raises(SemanticIRCallBoundaryError, match="call arguments disagree"):
        bind_reports(semantic, _calls(), contract=_contract())


def test_different_source_or_stage1_blocks() -> None:
    calls = _calls()
    calls["canonical_source"]["sha256"] = "c" * 64
    with pytest.raises(SemanticIRCallBoundaryError, match="different canonical source"):
        bind_reports(_semantic(), calls, contract=_contract())

    calls = _calls()
    calls["stage1"]["sha256"] = "d" * 64
    with pytest.raises(SemanticIRCallBoundaryError, match="different Stage1 artifact"):
        bind_reports(_semantic(), calls, contract=_contract())


def test_native_capacity_report_may_not_claim_semantic_linkage_authority() -> None:
    calls = _calls()
    calls["qualification"]["semantic_call_linkage_complete_from_this_report_alone"] = True
    with pytest.raises(SemanticIRCallBoundaryError, match="must not claim semantic linkage"):
        bind_reports(_semantic(), calls, contract=_contract())
