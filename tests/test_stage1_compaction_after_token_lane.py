from __future__ import annotations

from tools.patch_stage1_codegen_ir_v2_capacity import (
    NEW_DISCARD_EVENT_BLOCK,
    OLD_DISCARD_EVENT_BLOCK,
)
from tools.patch_stage1_compaction_after_token_lane import (
    build_compacted_candidate,
    build_token_lane_candidate,
)
from tools.patch_stage1_token_lane_wide_literals import SOURCE


def test_compaction_is_applied_only_after_token_lane_repair() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    token_lane = build_token_lane_candidate(source)
    compacted = build_compacted_candidate(source)

    assert token_lane != source
    assert compacted != token_lane
    assert "return pack_token(position, 2, number * negative)" not in compacted
    assert "return pack_token(position, 2, 0)" in compacted
    assert OLD_DISCARD_EVENT_BLOCK not in compacted
    assert NEW_DISCARD_EVENT_BLOCK in compacted


def test_composed_candidate_does_not_add_functions_or_locals() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    compacted = build_compacted_candidate(source)

    assert compacted.count("fn ") == source.count("fn ")
    assert compacted.count("mut ") == source.count("mut ")


def test_compaction_textual_delta_stays_narrow_after_token_repair() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    token_lane = build_token_lane_candidate(source)
    compacted = build_compacted_candidate(source)

    assert token_lane.count("ir_ast_event_opcode = 5") == 1
    assert token_lane.count("ir_ast_event_operand = value") >= 1
    assert compacted.count("ir_ast_event_opcode = 5") == 0
    assert len(token_lane.encode("utf-8")) - len(compacted.encode("utf-8")) == 101
