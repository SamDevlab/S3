"""Contract tests for research-only live-boundary summaries."""

from __future__ import annotations

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64.liveness import analyze_liveness
from tools.s3_111_live_range_experiments import summarize_liveness


def test_summary_preserves_cfg_backedge_liveness_and_is_deterministic() -> None:
    program = parse_assembly(
        """
        .function loop_test -> tryte
            .register r0, tryte
            .register r1, tryte
        .label entry
            TCONST r0, 2
            TCONST r1, 0
            TJMP header
        .label header
            TBR3 r0, body, exit, exit
        .label body
            TADD r1, r1, r0
            TJMP header
        .label exit
            TRET r1
        .end
        """
    )
    function = program.functions[0]

    live = analyze_liveness(function)
    summary = summarize_liveness(function)

    assert live.blocks["header"].live_in == frozenset({0, 1})
    assert live.blocks["body"].live_out == frozenset({0, 1})
    assert summary == summarize_liveness(function)
    assert summary["block_count"] == 4
    assert summary["instruction_count"] == 7
    assert summary["peak_live_virtual_registers"] == 2
    assert summary["registers_live_across_multiple_blocks"] == 2
    assert "global linear live-range length" in summary["metric_contract"]
