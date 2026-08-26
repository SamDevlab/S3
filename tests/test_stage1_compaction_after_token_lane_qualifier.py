from __future__ import annotations

import pytest

from tools.qualify_stage1_compaction_after_token_lane import (
    _block_guard,
    _event_count_guard,
    _input_delta_guards,
    _same_input_ast,
    _validate_token_prerequisite,
)


def _audit(**overrides: int) -> dict[str, int]:
    base = {
        "function_count": 34,
        "foreign_count": 5,
        "parameter_count": 64,
        "local_count": 100,
        "ast_assignment_count": 300,
        "ast_call_count": 800,
        "ast_return_count": 110,
        "ast_match_count": 90,
        "ast_while_count": 10,
        "ast_break_count": 4,
        "ast_binop_count": 180,
        "ast_comparison_count": 100,
        "ast_cast_count": 0,
        "ast_discard_count": 750,
        "ir_block_count": 350,
        "ir_instruction_count": 1460,
    }
    base.update(overrides)
    return base


def test_token_prerequisite_rejects_nonpass() -> None:
    source = b"candidate"
    report = {
        "canonical_source_mutated": False,
        "candidate": {"source_sha256": "no", "source_bytes": len(source)},
        "qualification": {"token_lane_candidate": "FAIL"},
    }
    with pytest.raises(ValueError, match="PASS is required"):
        _validate_token_prerequisite(report, source)


def test_same_input_ast_ignores_ir_capacity_fields() -> None:
    left = {"audit": _audit(ir_instruction_count=1460, ir_block_count=365)}
    right = {"audit": _audit(ir_instruction_count=1200, ir_block_count=340)}
    guards = _same_input_ast(left, right)
    assert all(guards.values())


def test_event_guard_models_hard_capacity_without_relabeling_full_count() -> None:
    capped = {"audit": _audit(ir_instruction_count=1460)}
    complete = {"audit": _audit(ir_instruction_count=1200)}
    assert _event_count_guard(capped, 2000) is True
    assert _event_count_guard(complete, 1200) is True
    assert _event_count_guard(complete, 1201) is False


def test_input_source_delta_requires_minus_two_assignments_only() -> None:
    s0 = {"audit": _audit(ast_assignment_count=300)}
    s1 = {"audit": _audit(ast_assignment_count=298)}
    guards = _input_delta_guards(s0, s1)
    assert all(guards.values())

    wrong = {"audit": _audit(ast_assignment_count=299)}
    assert _input_delta_guards(s0, wrong)["assignment_delta_minus_two"] is False


def test_block_equality_not_applicable_under_event_truncation() -> None:
    e0 = {"audit": _audit(ir_block_count=365)}
    e1 = {"audit": _audit(ir_block_count=329)}
    result = _block_guard(e0, e1, e0_full_events=2000, e1_full_events=1200)
    assert result["applicable"] is False
    assert result["pass"] is None
    assert result["reason"] == "EVENT_STREAM_TRUNCATION_PRESENT"


def test_block_equality_required_when_both_event_streams_fit() -> None:
    e0 = {"audit": _audit(ir_block_count=329)}
    e1 = {"audit": _audit(ir_block_count=329)}
    result = _block_guard(e0, e1, e0_full_events=1300, e1_full_events=1000)
    assert result["applicable"] is True
    assert result["pass"] is True

    mismatch = {"audit": _audit(ir_block_count=330)}
    assert _block_guard(e0, mismatch, e0_full_events=1300, e1_full_events=1000)["pass"] is False
