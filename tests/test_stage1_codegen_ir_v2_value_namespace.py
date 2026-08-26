from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.audit_stage1_codegen_ir_v2_value_namespace import (
    CONTRACT,
    INLINE_LITERAL_MAX,
    INLINE_LITERAL_MIN,
    PARAMETER_CAPACITY,
    PAYLOAD_DOMAIN,
    SIGNED_I64_MAX,
    SOURCE,
    audit,
    decode_inline_literal,
    encode_inline_literal,
    header_limit,
    pack_header,
    unpack_header,
)


ROOT = Path(__file__).resolve().parents[1]


def test_packed_value_header_boundary_round_trip_and_contract_bound() -> None:
    fields = (7, 64, 365, 1460)
    record = pack_header(*fields)
    assert record == header_limit() == 278057519
    assert record < SIGNED_I64_MAX
    assert unpack_header(record) == fields


@pytest.mark.parametrize("value", [INLINE_LITERAL_MIN, -1, 0, 1, INLINE_LITERAL_MAX])
def test_inline_literal_round_trip(value: int) -> None:
    encoded = encode_inline_literal(value)
    assert 0 <= encoded < PAYLOAD_DOMAIN
    assert decode_inline_literal(encoded) == value


@pytest.mark.parametrize("value", [INLINE_LITERAL_MIN - 1, INLINE_LITERAL_MAX + 1])
def test_wide_literal_boundary_is_fail_closed(value: int) -> None:
    with pytest.raises(ValueError, match="wide representation"):
        encode_inline_literal(value)


def test_current_value_storage_design_is_static_only_and_legacy_is_not_semantic() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    result = audit(SOURCE.read_text(encoding="utf-8"), contract)
    assert result["status"] == "STATIC_VALUE_NAMESPACE_DESIGN_PASS"
    assert result["legacy_storage"]["total_slots"] == 1460
    assert len(result["legacy_storage"]["banks"]) == 4
    assert result["legacy_storage"]["contents"] == "STRUCTURAL_NUMERIC_TOKEN_RECORDS_NOT_SEMANTIC_VALUES"
    assert result["parameter_metadata"]["capacity_bound"] == PARAMETER_CAPACITY == 68
    assert result["parameter_metadata"]["semantic_id_domain"] == "[0,parameter_count)"
    assert result["parameter_metadata"]["fixed_64_reservation"] is False
    assert result["namespace"]["local_start"] == "parameter_count"
    assert result["namespace"]["local_id_rule"] == "parameter_count + global_local_record_index"
    assert result["native_evidence"] is False
    assert result["canonical_source_mutated"] is False
    assert result["next"] == "WAIT_FOR_NATIVE_LOCAL_PASS_THEN_BUILD_EXACT_VALUE_NAMESPACE_PREFLIGHT"


def test_contract_forbids_fixed_64_reservation_and_silent_value_reinterpretation() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    layout = contract["semantic_id_layout"]
    assert layout["parameter_capacity_bound"] == 68
    assert layout["parameter_domain"] == "[0,parameter_count)"
    assert layout["local_domain_start"] == "parameter_count"
    assert layout["dynamic_start"] == "parameter_count + local_record_count"
    assert layout["fixed_64_parameter_reservation"] is False
    assert contract["physical_storage"]["silent_reinterpretation_allowed"] is False
    assert contract["constant_representation"]["deduplicate_repeated_literals"] is True
    assert contract["constant_representation"]["wide_literal"]["extension_slot_is_semantic_value_id"] is False
    prohibited = set(contract["prohibited_shortcuts"])
    assert "reinterpret legacy ir_value_records as semantic IDs without rebuild" in prohibited
    assert "restore or assume a fixed [0,64) parameter semantic-ID reservation" in prohibited
    assert "one semantic value per lexical zero initializer occurrence" in prohibited


def test_new_ir_v2_python_tooling_files_compile_syntactically() -> None:
    paths = (
        "tools/audit_stage1_codegen_ir.py",
        "tools/audit_stage1_codegen_ir_v2_call_arguments.py",
        "tools/audit_stage1_codegen_ir_v2_value_namespace.py",
        "tools/patch_stage1_codegen_ir_v2_locals.py",
        "tools/preflight_stage1_codegen_ir_v2_locals.py",
        "tools/qualify_stage1_codegen_ir_v2_locals.py",
        "tools/qualify_stage1_codegen_ir_v2_full_chain.py",
    )
    for relative in paths:
        path = ROOT / relative
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")
