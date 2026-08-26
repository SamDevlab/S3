from __future__ import annotations

from tools.patch_stage1_codegen_ir_v2_parameters_after_token_lane import (
    build_candidate,
)
from tools.patch_stage1_token_lane_wide_literals import SOURCE


def test_rebased_parameter_candidate_contains_all_three_prerequisites() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    candidate = build_candidate(source)

    assert candidate != source
    assert "return pack_token(position, 2, number * negative)" not in candidate
    assert "return pack_token(position, 2, 0)" in candidate
    assert "ir_ast_event_opcode = 5" not in candidate
    assert "mut ir_parameter_records: i64[64]" in candidate
    assert "pending_parameter_index = parameter_count" in candidate
    assert "parameter_verify_value == parameter_verify_index" in candidate


def test_rebased_parameter_candidate_is_deterministic() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert build_candidate(source) == build_candidate(source)
