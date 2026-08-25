from __future__ import annotations

import pytest

from tools.audit_stage1_codegen_ir_v2_local_metadata import (
    FRAME_SLOT_DOMAIN,
    FUNCTION_DOMAIN,
    MUTABILITY_DOMAIN,
    NAME_DOMAIN,
    SIGNED_I64_MAX,
    SOURCE,
    TYPE_DOMAIN,
    VALUE_ID_DOMAIN,
    audit,
    local_record_limit,
    pack_local,
    unpack_local,
)


def test_packed_local_boundary_round_trip() -> None:
    fields = (
        FUNCTION_DOMAIN - 1,
        NAME_DOMAIN - 1,
        TYPE_DOMAIN - 1,
        MUTABILITY_DOMAIN - 1,
        FRAME_SLOT_DOMAIN - 1,
        VALUE_ID_DOMAIN - 1,
    )
    record = pack_local(*fields)
    assert record == local_record_limit()
    assert record <= SIGNED_I64_MAX
    assert unpack_local(record) == fields


@pytest.mark.parametrize(
    ("index", "bad_value"),
    [
        (0, FUNCTION_DOMAIN),
        (1, NAME_DOMAIN),
        (2, TYPE_DOMAIN),
        (3, MUTABILITY_DOMAIN),
        (4, FRAME_SLOT_DOMAIN),
        (5, VALUE_ID_DOMAIN),
    ],
)
def test_packed_local_rejects_out_of_domain(index: int, bad_value: int) -> None:
    fields = [0, 0, 0, 0, 0, 0]
    fields[index] = bad_value
    with pytest.raises(ValueError, match="outside packed-local domain"):
        pack_local(*fields)


def test_current_source_supports_local_metadata_design_without_existing_lane() -> None:
    result = audit(SOURCE.read_text(encoding="utf-8"))
    assert result["status"] == "STATIC_LOCAL_METADATA_DESIGN_PASS"
    assert result["observed"]["existing_local_record_arrays"] == []
    assert result["guards"]["mut_keyword_is_current_local_signal"] is True
    assert result["guards"]["current_function_state_exists"] is True
    assert result["guards"]["packed_local_record_fits_signed_i64"] is True
    assert result["candidate_record"]["planned_value_id_range"] == {
        "start": 64,
        "end_exclusive": 128,
    }
    assert result["parser_strategy"]["frame_slot"]["requires_new_large_array"] is False
    assert result["local_transform"] == "NOT_IMPLEMENTED"


def test_local_design_audit_fails_if_mut_signal_disappears() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    mutated = source.replace("local_count += 1", "local_count += 0", 1)
    assert mutated != source
    result = audit(mutated)
    assert result["status"] == "STATIC_LOCAL_METADATA_DESIGN_FAIL"
    assert result["guards"]["mut_keyword_is_current_local_signal"] is False


def test_local_design_audit_fails_if_existing_lane_would_be_silently_reinterpreted() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    anchor = "    mut ir_opcode: tryte[64] = "
    injected = "    mut ir_local_records: i64[64] = [0]\n" + anchor
    mutated = source.replace(anchor, injected, 1)
    assert mutated != source
    result = audit(mutated)
    assert result["status"] == "STATIC_LOCAL_METADATA_DESIGN_FAIL"
    assert result["guards"]["no_existing_local_record_array_to_silently_reinterpret"] is False


def test_boolean_local_field_is_rejected() -> None:
    with pytest.raises(ValueError, match="owner outside packed-local domain"):
        pack_local(True, 1, 1, 1, 1, 1)
