from __future__ import annotations

from pathlib import Path

from tools.audit_stage1_semantic_ir_requirements import audit


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_source_requires_lossless_typed_ir_before_general_emitter() -> None:
    result = audit(ROOT / "selfhost" / "compiler" / "s3c_stage1.s3")

    assert result["status"] == "BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP"
    semantic = result["parser_semantic_audit"]
    assert semantic["functions"] == 32
    assert semantic["foreign_functions"] == 5
    assert semantic["parameters"] == 70
    assert semantic["local_declarations"] == 274
    assert semantic["calls"] == 940
    assert semantic["call_arguments"] == 1101
    assert result["required_operations"]["CALL_INTERNAL"] is True
    assert result["required_operations"]["CALL_FOREIGN"] is True
    assert result["required_operations"]["BRANCH"] is True
    assert result["required_operations"]["INDEX_LOAD_OR_STORE"] is True
    assert result["stage1_self_emit"] == (
        "BLOCKED_UNTIL_MISSING_LANES_EXIST_AND_VERIFY"
    )
    assert result["reference_typed_ir"]["status"] == "NOT_MEASURED_BY_DEFAULT"
    assert len(result["missing_lossless_typed_lanes"]) >= 6

    storage = result["storage_evidence"]
    assert storage["parameter_metadata"] == {
        "status": "PARTIAL",
        "capacity": 68,
        "fields_preserved": [
            "owner_function",
            "name_identity",
            "ordinal",
            "declared_type",
        ],
        "fields_missing": [
            "mutability",
            "semantic_value_id",
        ],
        "source_prefixes": [
            "ir_parameter_owner",
            "ir_parameter_name",
            "ir_parameter_ordinal",
            "ir_parameter_type",
        ],
    }
    assert storage["event_record_schema"]["schema"] == (
        "packed(opcode, owner_function_plus_one, token_operand, token_offset)"
    )
    assert storage["event_record_schema"]["operand_assignment_sources"] == [
        "previous_value",
        "value",
    ]
    assert storage["event_record_schema"]["pack_expression_count"] == 1
    assert storage["instruction_cardinality"]["derived_from_event_count"] is True
    assert storage["legacy_instruction_records"]["read_count"] == 0
    relationships = storage["semantic_relationships"]
    assert all(value is False for value in relationships.values())
