from __future__ import annotations

from tools.audit_stage1_instruction_stream_contract import audit


def _requirements() -> dict[str, object]:
    return {
        "missing_lossless_typed_lanes": ["instruction_operands_results_and_order"],
        "reference_typed_ir": {
            "status": "MEASURED_HOST_IR_ORACLE_NOT_STAGE1_EVIDENCE",
            "instructions": 49128,
            "max_instructions_per_function": 45000,
            "instruction_results": 32630,
        },
        "storage_evidence": {
            "legacy_instruction_records": {
                "declaration_count": 2,
                "write_count": 9,
                "read_count": 0,
            },
            "semantic_relationships": {
                "instruction_operand_value_ids": False,
                "instruction_result_value_ids": False,
            },
        },
    }


def _contract() -> dict[str, object]:
    return {
        "physical_strategy": {
            "kind": "STREAMING_SERIALIZED_RECORDS",
            "fixed_instruction_matrix_allowed": False,
            "legacy_ir_instruction_records_semantic_reuse_allowed": False,
        },
        "logical_instruction": {
            "fields": [
                "instruction_id",
                "owner_block_id",
                "ordinal_in_block",
                "opcode",
                "operand_value_ids",
                "result_value_ids",
            ]
        },
        "verifier_requirements": [
            "a",
            "b",
            "c",
            "d",
            "e",
            "f",
        ],
    }


def test_streaming_design_is_required_by_current_scale() -> None:
    result = audit(_requirements(), _contract())

    assert result["status"] == "STATIC_INSTRUCTION_STREAM_DESIGN_PASS"
    assert result["oracle"]["instructions"] == 49128
    assert result["legacy_instruction_lane"]["estimated_physical_slots"] == 730
    assert result["legacy_instruction_lane"]["reads"] == 0
    assert result["contract_strategy"] == "STREAMING_SERIALIZED_RECORDS"
    assert result["native_evidence"] is False


def test_fixed_matrix_shortcut_fails_static_contract() -> None:
    contract = _contract()
    contract["physical_strategy"]["fixed_instruction_matrix_allowed"] = True
    result = audit(_requirements(), contract)

    assert result["status"] == "STATIC_INSTRUCTION_STREAM_DESIGN_RECONCILE"
    assert result["guards"]["contract_forbids_fixed_matrix"] is False
