from __future__ import annotations

from tools.patch_stage1_codegen_ir_v2_capacity import transform as compact_discard_events
from tools.patch_stage1_codegen_ir_v2_parameters import (
    PARAMETER_CAPACITY,
    build_candidate,
    transform_parameters,
)
from tools.preflight_stage1_codegen_ir_v2_parameters import build_preflight
from tools.promote_stage1_codegen_ir_v2_capacity import SOURCE


def test_parameter_candidate_is_deterministic_and_packed() -> None:
    baseline = SOURCE.read_text(encoding="utf-8")
    first = build_candidate(baseline)
    second = build_candidate(baseline)

    assert first == second
    assert first.count("mut ir_parameter_records: i64[64]") == 1
    assert "ir_ast_event_opcode = 5" not in first
    assert "pending_parameter_index = parameter_count" in first
    assert "pending_parameter_name = previous_value" in first
    assert "parameter_verify_value == parameter_verify_index" in first
    assert PARAMETER_CAPACITY == 64


def test_parameter_transform_requires_compaction_first() -> None:
    baseline = SOURCE.read_text(encoding="utf-8")
    try:
        transform_parameters(baseline)
    except ValueError as error:
        assert "requires discard-event compaction first" in str(error)
    else:
        raise AssertionError("parameter transform accepted uncompacted source")


def test_parameter_transform_is_single_use() -> None:
    baseline = SOURCE.read_text(encoding="utf-8")
    compacted = compact_discard_events(baseline)
    candidate = transform_parameters(compacted)

    try:
        transform_parameters(candidate)
    except ValueError as error:
        assert "already exists" in str(error)
    else:
        raise AssertionError("parameter transform applied twice")


def test_parameter_phase_adds_no_function_signatures() -> None:
    baseline = SOURCE.read_text(encoding="utf-8")
    compacted = compact_discard_events(baseline)
    candidate = transform_parameters(compacted)

    assert candidate.count("\nfn ") == compacted.count("\nfn ")
    assert candidate.count("\nforeign fn ") == compacted.count("\nforeign fn ")


def test_parameter_preflight_is_bounded_and_not_native_evidence() -> None:
    baseline = SOURCE.read_text(encoding="utf-8")
    report = build_preflight(baseline)

    assert report["native_evidence"] is False
    assert report["storage_strategy"]["physical_lanes"] == 1
    assert report["storage_strategy"]["parameter_capacity"] == 64
    assert report["guards"]["no_new_function_signatures"] is True
    assert report["guards"]["single_packed_parameter_lane"] is True
    assert report["guards"]["discard_compaction_retained"] is True
    assert report["capacity_projection"]["projected_values_upper_bound"] < report["capacity_projection"]["value_capacity"]
    assert report["capacity_projection"]["projected_blocks_upper_bound"] < report["capacity_projection"]["block_capacity"]
    assert report["preflight_pass"] is True
