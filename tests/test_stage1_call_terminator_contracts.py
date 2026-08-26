from __future__ import annotations

from tools.audit_stage1_call_terminator_contracts import audit


def _requirements() -> dict[str, object]:
    return {
        "reference_typed_ir": {
            "status": "MEASURED_HOST_IR_ORACLE_NOT_STAGE1_EVIDENCE",
            "call_kinds": {"internal": 795, "foreign": 22},
            "terminators": {"branch3": 740, "jump": 2127, "return": 120},
        },
        "storage_evidence": {
            "semantic_relationships": {
                "call_argument_value_ids": False,
                "call_result_value_ids": False,
                "complete_terminator_values": False,
            }
        },
    }


def _call_contract() -> dict[str, object]:
    return {
        "logical_call": {
            "fields": [
                "defining_instruction_id",
                "argument_value_ids",
                "result_value_ids",
            ],
            "callee_kinds": ["INTERNAL", "FOREIGN"],
        },
        "foreign_abi": {
            "required_fields": [
                "foreign_symbol_identity",
                "parameter_types",
                "return_type",
                "argument_value_ids",
                "result_value_ids",
            ]
        },
    }


def _terminator_contract() -> dict[str, object]:
    return {
        "compact_block_candidate_scope": {
            "classification": "STRUCTURAL_CAPACITY_ONLY",
            "closes_complete_terminator_lane": False,
        },
        "terminator_kinds": {
            "RETURN": {
                "required": ["owner_block_id", "return_value_id"],
                "target_count": 0,
            },
            "JUMP": {
                "required": ["owner_block_id", "target_block_id"],
                "target_count": 1,
            },
            "BRANCH3": {
                "required": [
                    "owner_block_id",
                    "condition_value_id",
                    "negative_target_block_id",
                    "zero_target_block_id",
                    "positive_target_block_id",
                ],
                "target_count": 3,
            },
        },
    }


def test_call_and_terminator_contracts_are_static_only_and_complete_in_shape() -> None:
    result = audit(_requirements(), _call_contract(), _terminator_contract())

    assert result["status"] == "STATIC_CALL_TERMINATOR_DESIGN_PASS"
    assert result["compact_block_native_result_required_for_w4"] is True
    assert result["call_linkage_native_allowed_now"] is False
    assert result["terminator_native_allowed_now"] is False
    assert result["terminator_guards"]["branch3_has_three_targets"] is True
    assert result["terminator_guards"]["compact_block_candidate_does_not_close_w4"] is True


def test_two_target_compact_block_record_cannot_claim_w4_closure() -> None:
    terminator = _terminator_contract()
    terminator["compact_block_candidate_scope"]["closes_complete_terminator_lane"] = True
    result = audit(_requirements(), _call_contract(), terminator)

    assert result["status"] == "STATIC_CALL_TERMINATOR_DESIGN_RECONCILE"
    assert result["terminator_guards"]["compact_block_candidate_does_not_close_w4"] is False
