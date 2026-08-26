from __future__ import annotations

from tools.audit_stage2_serialized_ir_envelope import audit


def _requirements() -> dict[str, object]:
    return {
        "status": "BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP",
        "storage_evidence": {
            "semantic_relationships": {
                "typed_value_definitions": False,
                "instruction_operand_value_ids": False,
                "instruction_result_value_ids": False,
                "call_argument_value_ids": False,
                "call_result_value_ids": False,
                "complete_terminator_values": False,
                "canonical_serialized_ir": False,
            }
        },
    }


def _contract() -> dict[str, object]:
    return {
        "prerequisite": {
            "all_required_native_gates_must_pass": True,
            "stage2_creation_allowed_before_prerequisites": False,
        },
        "envelope": {"magic": "S3IR2", "schema_version": 1},
        "completeness_bits": {
            "1": "W1",
            "2": "W2",
            "4": "W3",
            "8": "W4",
        },
        "required_completeness_mask": 15,
        "stage1_emission_rules": [
            "do not emit the S3IR2 magic unless completeness_mask == 15"
        ],
        "stage2_acceptance_rules": ["reject completeness_mask != 15"],
    }


def test_stage2_envelope_design_is_fail_closed_while_ir_is_incomplete() -> None:
    result = audit(_requirements(), _contract())

    assert result["status"] == "STATIC_STAGE2_ENVELOPE_DESIGN_PASS_FAIL_CLOSED"
    assert result["typed_workstreams_complete"] is False
    assert result["stage2_creation_allowed_now"] is False
    assert result["required_completeness_mask"] == 15
    assert result["stage2"] == "DESIGN_ONLY_NOT_CREATED"


def test_stage2_contract_rejects_premature_creation_permission() -> None:
    contract = _contract()
    contract["prerequisite"]["stage2_creation_allowed_before_prerequisites"] = True
    result = audit(_requirements(), contract)

    assert result["status"] == "STATIC_STAGE2_ENVELOPE_DESIGN_RECONCILE"
    assert result["guards"]["stage2_creation_forbidden_before_prerequisites"] is False
