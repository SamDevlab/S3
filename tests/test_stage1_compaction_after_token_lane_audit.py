from __future__ import annotations

from tools.audit_stage1_compaction_after_token_lane import (
    _events,
    _source_counts,
    audit,
)
from tools.patch_stage1_token_lane_wide_literals import SOURCE
from tools.qualify_stage1_compaction_after_token_lane import (
    _native_input_observation_guards,
    _source_delta_guards,
)


def test_same_input_compaction_only_removes_discard_events() -> None:
    source = "fn main() -> tryte:\n    discard helper(1)\n    return 7\n"
    baseline = _events(source, compact_discard_behavior=False)
    compacted_behavior = _events(source, compact_discard_behavior=True)

    assert [event for event in baseline if event[1] != 5] == compacted_behavior
    assert sum(1 for event in baseline if event[1] == 5) == 1
    assert all(event[1] != 5 for event in compacted_behavior)


def test_source_counts_keep_textual_and_semantic_axes_separate() -> None:
    source = "mut x: i64 = 5\ndiscard helper(x)\n"
    counts = _source_counts(source)

    assert counts["assignment_observation_tokens"] == 2  # mut + '='
    assert counts["numeric_tokens"] == 1
    assert counts["discard_keyword_tokens"] == 1


def test_real_composed_candidate_has_static_semantic_differential() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    result = audit(source)

    assert result["status"] == "STATIC_COMPACTION_SEMANTIC_DIFFERENTIAL_PASS_NATIVE_2X2_REQUIRED"
    assert all(result["guards"].values())
    assert result["source_input_delta"]["assignment_observation_tokens"] == -2
    assert result["source_input_delta"]["numeric_tokens"] == -1
    assert result["source_input_delta"]["discard_keyword_tokens"] == 0
    assert result["matrix"]["E1_S0_discard_events"] == 0
    assert result["matrix"]["E1_S1_discard_events"] == 0


def test_native_input_guard_does_not_infer_textual_assignment_delta() -> None:
    left = {"audit": {"ast_assignment_count": 75, "ast_discard_count": 699, "ast_match_count": 94, "ast_while_count": 6}}
    right = {"audit": {"ast_assignment_count": 73, "ast_discard_count": 699, "ast_match_count": 94, "ast_while_count": 6}}

    assert all(_native_input_observation_guards(left, right).values())


def test_source_delta_is_checked_separately_from_native_observations() -> None:
    assert all(
        _source_delta_guards(
            {"source_input_delta": {"assignment_observation_tokens": -2, "numeric_tokens": -1}}
        ).values()
    )
