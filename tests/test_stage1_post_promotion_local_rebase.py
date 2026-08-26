from __future__ import annotations

import pytest

from tools.audit_stage1_post_promotion_local_rebase import (
    LEGACY_LOCAL_TRANSFORM,
    LEGACY_VALUE_AUDIT,
    PARAMETER_VALUE_CANDIDATE,
    SIGNED_I64_MAX,
    SOURCE,
    audit,
    maximum_packed_local_record,
    pack_local_record,
)


def _current_audit() -> dict[str, object]:
    return audit(
        SOURCE.read_text(encoding="utf-8"),
        legacy_local_transform=LEGACY_LOCAL_TRANSFORM.read_text(encoding="utf-8"),
        legacy_value_audit=LEGACY_VALUE_AUDIT.read_text(encoding="utf-8"),
        parameter_value_candidate=PARAMETER_VALUE_CANDIDATE.read_text(encoding="utf-8"),
    )


def test_post_promotion_local_rebase_detects_stale_legacy_namespace() -> None:
    result = _current_audit()

    assert result["status"] == "STATIC_POST_PROMOTION_LOCAL_REBASE_DESIGN_PASS"
    assert result["native_evidence"] is False
    assert result["canonical_source_mutated"] is False
    assert result["legacy_tooling_disposition"]["status"] == "REBASE_REQUIRED_DO_NOT_CHAIN_AS_CANONICAL"
    assert result["canonical_parameter_metadata"]["capacity_bound"] == 68
    assert result["canonical_parameter_metadata"]["semantic_value_domain"] == "[0,parameter_count)"


def test_post_promotion_local_rebase_uses_dynamic_local_value_ids() -> None:
    result = _current_audit()
    contract = result["local_record_contract"]

    assert contract["semantic_value_id_rule"] == "parameter_count + global_local_record_slot"
    assert contract["physical_frame_offset"] == "DEFERRED_TO_EMITTER"
    assert "semantic_value_id" not in contract["fields"]
    assert result["compact_capture_contract"]["maximum_history_tokens"] == 7
    assert result["next"] == "IMPLEMENT_COMPACT_LOCAL_METADATA_CANDIDATE_WITH_DYNAMIC_PARAMETER_NAMESPACE"


def test_packed_local_record_boundary_fits_signed_i64() -> None:
    maximum = maximum_packed_local_record()
    assert 0 < maximum <= SIGNED_I64_MAX
    assert maximum == pack_local_record(63, 364, 364, 2, 364, 1460)


@pytest.mark.parametrize(
    ("args", "label"),
    [
        ((64, 0, 0, 1, 0, 1), "owner"),
        ((0, 365, 0, 1, 0, 1), "name_identity"),
        ((0, 0, 365, 1, 0, 1), "type_id"),
        ((0, 0, 0, 3, 0, 1), "storage_kind"),
        ((0, 0, 0, 1, 365, 1), "local_ordinal"),
        ((0, 0, 0, 1, 0, 1461), "fixed_extent"),
    ],
)
def test_packed_local_record_rejects_out_of_domain_values(
    args: tuple[int, int, int, int, int, int], label: str
) -> None:
    with pytest.raises(ValueError, match=label):
        pack_local_record(*args)
