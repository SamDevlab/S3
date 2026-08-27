from __future__ import annotations

from pathlib import Path

from bootstrap.s3.pipeline import compile_source


ROOT = Path(__file__).resolve().parents[1]
STREAM_SOURCE = ROOT / "selfhost" / "compiler" / "stage1_semantic_stream_v1.s3"


def test_semantic_stream_protocol_is_parseable_by_stage0() -> None:
    source = STREAM_SOURCE.read_text(encoding="utf-8")
    result = compile_source(source)
    assert result.ir is not None
    assert result.assembly is not None


def test_semantic_stream_protocol_covers_all_five_lane_record_families() -> None:
    source = STREAM_SOURCE.read_text(encoding="utf-8")
    for marker in (
        "fn semantic_emit_value(",
        "fn semantic_emit_instruction(",
        "fn semantic_emit_operand(",
        "fn semantic_emit_result(",
        "fn semantic_emit_call(",
        "fn semantic_emit_call_argument(",
        "fn semantic_emit_terminator(",
        "fn semantic_emit_complete(",
        "fn semantic_emit_header(",
    ):
        assert marker in source


def test_streaming_protocol_does_not_encode_semantic_identity_as_fixed_array_capacity() -> None:
    source = STREAM_SOURCE.read_text(encoding="utf-8")
    assert "[365]" not in source
    assert "[1460]" not in source
    assert "value_id" in source
    assert "instruction_id" in source
    assert "owner_function" in source


def test_decimal_emitter_is_not_limited_to_three_digits() -> None:
    source = STREAM_SOURCE.read_text(encoding="utf-8")
    assert "while probe >= 10:" in source
    assert "divisor = divisor * 10" in source
    assert "while divisor > 0:" in source
