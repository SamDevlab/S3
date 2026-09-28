from __future__ import annotations

from types import SimpleNamespace

import pytest

from bootstrap.s3.assembly import AssemblyOpcode
from tools.s3_111_edge_profile_analysis import _canonical_source_bytes, analyze_function


def _block(label: str, opcode: AssemblyOpcode, *targets: str) -> SimpleNamespace:
    instruction = SimpleNamespace(opcode=opcode, labels=tuple(targets))
    return SimpleNamespace(label=label, instructions=[instruction])


def _function(*blocks: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(name="f", blocks=list(blocks))


def test_unconditional_edge_count_is_exact_and_layout_opportunity_is_explicit() -> None:
    function = _function(
        _block("entry", AssemblyOpcode.TJMP, "body"),
        _block("exit", AssemblyOpcode.TRET),
        _block("body", AssemblyOpcode.TJMP, "exit"),
    )
    result = analyze_function(function, {("f", "entry"): 12, ("f", "body"): 7})

    entry, body = result["edges"]
    assert (entry["edge_executions"], entry["count_status"]) == (12, "EXACT_SINGLE_SUCCESSOR")
    assert entry["fallthrough_candidate_eligibility"] is True
    assert (body["edge_executions"], body["count_status"]) == (7, "EXACT_SINGLE_SUCCESSOR")
    assert body["fallthrough_candidate_eligibility"] is True


def test_conditional_edges_remain_unknown_even_with_source_count() -> None:
    function = _function(
        _block("branch", AssemblyOpcode.TBR3, "negative", "neutral", "positive"),
        _block("negative", AssemblyOpcode.TRET),
        _block("neutral", AssemblyOpcode.TRET),
        _block("positive", AssemblyOpcode.TRET),
    )
    result = analyze_function(function, {("f", "branch"): 100})

    assert [edge["edge_executions"] for edge in result["edges"]] == [None, None, None]
    assert {edge["count_status"] for edge in result["edges"]} == {"CONDITIONAL_EDGE_COUNT_UNOBSERVED"}
    assert not any(edge["fallthrough_candidate_eligibility"] for edge in result["edges"])


def test_edge_source_missing_from_reported_hot_subset_stays_unknown() -> None:
    function = _function(_block("entry", AssemblyOpcode.TJMP, "exit"), _block("exit", AssemblyOpcode.TRET))
    result = analyze_function(function, {})

    assert result["edges"][0]["edge_executions"] is None
    assert result["edges"][0]["count_status"] == "SOURCE_BLOCK_COUNT_NOT_REPORTED"


def test_missing_target_fails_closed() -> None:
    function = _function(_block("entry", AssemblyOpcode.TJMP, "absent"))

    with pytest.raises(ValueError, match="missing target"):
        analyze_function(function, {("f", "entry"): 1})


def test_duplicate_block_labels_fail_closed() -> None:
    function = _function(_block("same", AssemblyOpcode.TRET), _block("same", AssemblyOpcode.TRET))

    with pytest.raises(ValueError, match="duplicate basic-block label"):
        analyze_function(function, {})


def test_source_identity_normalizes_windows_and_legacy_newlines_to_canonical_lf() -> None:
    assert _canonical_source_bytes(b"a\r\nb\rc\n") == b"a\nb\nc\n"
