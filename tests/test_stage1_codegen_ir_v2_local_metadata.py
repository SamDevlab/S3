from __future__ import annotations

import pytest

from tools.audit_stage1_codegen_ir_v2_local_metadata import (
    EXTENT_DOMAIN,
    FUNCTION_DOMAIN,
    LOCAL_ORDINAL_DOMAIN,
    MUTABILITY_DOMAIN,
    NAME_DOMAIN,
    SIGNED_I64_MAX,
    SOURCE,
    STORAGE_KIND_DOMAIN,
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
        STORAGE_KIND_DOMAIN - 1,
        LOCAL_ORDINAL_DOMAIN - 1,
        EXTENT_DOMAIN - 1,
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
        (4, STORAGE_KIND_DOMAIN),
        (5, LOCAL_ORDINAL_DOMAIN),
        (6, EXTENT_DOMAIN),
        (7, VALUE_ID_DOMAIN),
    ],
)
def test_packed_local_rejects_out_of_domain(index: int, bad_value: int) -> None:
    fields = [0, 0, 0, 0, 0, 0, 0, 0]
    fields[index] = bad_value
    with pytest.raises(ValueError, match="outside packed-local domain"):
        pack_local(*fields)


def test_current_source_supports_shape_preserving_local_metadata_design() -> None:
    result = audit(SOURCE.read_text(encoding="utf-8"))
    assert result["status"] == "STATIC_LOCAL_METADATA_DESIGN_PASS"
    assert result["observed"]["existing_local_record_arrays"] == []
    assert result["guards"]["mut_keyword_is_current_local_signal"] is True
    assert result["guards"]["current_function_state_exists"] is True
    assert result["guards"]["packed_local_record_fits_signed_i64"] is True
    assert result["guards"]["observed_fixed_array_extents_fit_record_domain"] is True
    assert result["observed"]["fixed_array_declaration_lines"] > 0
    assert result["candidate_record"]["storage_kinds"] == {
        "1": "SCALAR",
        "2": "FIXED_ARRAY",
    }
    assert result["candidate_record"]["parameter_value_id_domain_reserved"] == [0, 64]
    assert result["parser_strategy"]["local_ordinal"].endswith(
        "physical frame/static offset is emitter-owned"
    )
    assert result["parser_strategy"]["array_shape"].startswith("storage_kind=2")
    assert result["local_transform"] == "PREPARATION_ALLOWED_REPORT_GATED"


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
        pack_local(True, 1, 1, 1, 1, 1, 1, 1)


def test_scalar_and_fixed_array_shapes_are_distinct_records() -> None:
    scalar = pack_local(1, 2, 67, 1, 1, 1, 1, 65)
    array = pack_local(1, 2, 67, 1, 2, 1, 365, 65)
    assert scalar != array
    assert unpack_local(scalar)[4:7] == (1, 1, 1)
    assert unpack_local(array)[4:7] == (2, 1, 365)
