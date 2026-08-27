from __future__ import annotations

import pytest

from tools.stage1_semantic_stream_protocol import (
    COMPLETE_MASK,
    SemanticStreamError,
    build_stream_from_source,
    parse_stream,
    verify_stream,
)


SOURCE = """\
fn add(a: i64, b: i64) -> i64:
    return a + b

fn main() -> i64:
    value: i64 = add(20, 22)
    match value <=> 42:
        -1:
            return -1
        0:
            return value
        1:
            return 1
"""


def test_reference_stream_round_trip_is_complete_and_verifiable() -> None:
    stream, reference, verification = build_stream_from_source(SOURCE)

    assert stream.startswith("S3IR2 1\n")
    assert stream.rstrip().endswith(f"Z {COMPLETE_MASK}")
    assert reference["status"] == "PASS"
    assert verification["status"] == "PASS"
    assert verification["complete"] is True
    assert verification["value_count"] > 0
    assert verification["instruction_count"] > 0
    assert verification["terminator_count"] > 0


def test_stream_contains_value_instruction_call_and_terminator_records() -> None:
    stream, _reference, _verification = build_stream_from_source(SOURCE)
    tags = {line.split()[0] for line in stream.splitlines()[1:]}
    assert {"V", "I", "O", "R", "C", "A", "T", "Z"} <= tags


def test_missing_header_fails_closed() -> None:
    with pytest.raises(SemanticStreamError):
        parse_stream("V 0 0 1 3 -1 -1 0 -1\nZ 15\n")


def test_unknown_value_reference_is_blocked() -> None:
    parsed = parse_stream(
        "S3IR2 1\n"
        "V 0 0 1 3 -1 -1 0 -1\n"
        "I 0 0 0 0 23 0 1 -1 -1\n"
        "O 0 0 99\n"
        "T 0 1 -1 -1 -1 -1 99\n"
        "Z 15\n"
    )
    verification = verify_stream(parsed)
    assert verification["status"] == "BLOCKED"
    assert any("unknown value 99" in error for error in verification["errors"])


def test_incomplete_mask_never_promotes_stream() -> None:
    parsed = parse_stream("S3IR2 1\nZ 7\n")
    verification = verify_stream(parsed)
    assert verification["complete"] is False
    assert verification["status"] == "BLOCKED"
