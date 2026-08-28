from __future__ import annotations

import pytest

from tools.patch_stage1_codegen_ir_v2_capacity import transform as compact_discard_events
from tools.patch_stage1_codegen_ir_v2_parameters import (
    PARAMETER_CAPACITY,
    build_candidate,
    has_explicit_parameter_metadata,
    transform_parameters,
)
from tools.preflight_stage1_codegen_ir_v2_parameters import build_preflight
from tools.promote_stage1_codegen_ir_v2_capacity import SOURCE


def test_packed_parameter_candidate_rejects_advanced_canonical_source() -> None:
    baseline = SOURCE.read_text(encoding="utf-8")
    assert has_explicit_parameter_metadata(baseline) is True
    with pytest.raises(ValueError, match="packed parameter candidate is stale"):
        build_candidate(baseline)
    assert PARAMETER_CAPACITY == 64


def test_parameter_transform_requires_compaction_first() -> None:
    baseline = SOURCE.read_text(encoding="utf-8")
    try:
        transform_parameters(baseline)
    except ValueError as error:
        assert "requires discard-event compaction first" in str(error)
    else:
        raise AssertionError("parameter transform accepted uncompacted source")


def test_parameter_transform_does_not_reconstruct_from_advanced_source() -> None:
    baseline = SOURCE.read_text(encoding="utf-8")
    compacted = compact_discard_events(baseline)
    with pytest.raises(ValueError, match="parameter declaration capture"):
        transform_parameters(compacted)


def test_current_source_owns_explicit_parameter_metadata() -> None:
    baseline = SOURCE.read_text(encoding="utf-8")
    assert has_explicit_parameter_metadata(baseline) is True


def test_parameter_preflight_is_bounded_and_not_native_evidence() -> None:
    baseline = SOURCE.read_text(encoding="utf-8")
    report = build_preflight(baseline)

    assert report["native_evidence"] is False
    assert report["status"] == "BLOCKED_PACKED_PARAMETER_CANDIDATE_STALE"
    assert report["current_source_has_explicit_parameter_metadata"] is True
    assert report["preflight_pass"] is False
