from __future__ import annotations

from tools.stage1_semantic_stream_v2 import (
    COMPLETE_MASK,
    build_stream,
    parse_stream,
    verify_stream,
)
from tools.verify_stage1_semantic_conformance_v2 import verify_conformance


SOURCE = """\
fn identity(value: i64) -> i64:
    return value

fn add_one(value: i64) -> i64:
    mut result: i64 = value + 1
    return result

fn classify(value: i64) -> i64:
    match value <=> 0:
        -1:
            return -1
        0:
            return 0
        1:
            return 1

fn main() -> i64:
    return add_one(identity(2))
"""


def test_v2_oracle_closes_all_five_lanes() -> None:
    stream, model, verification = build_stream(SOURCE)
    parsed = parse_stream(stream)
    assert parsed["completeness_mask"] == COMPLETE_MASK
    assert parsed["complete"] is True
    assert verification["status"] == "PASS"
    assert all(model["completeness"].values())
    tags = {record["tag"] for record in parsed["records"]}
    assert {"F", "B", "V", "I", "O", "R", "C", "A", "T", "Z"} <= tags


def test_v2_round_trip_is_strictly_conformant() -> None:
    stream, _model, _verification = build_stream(SOURCE)
    result = verify_conformance(SOURCE, stream)
    assert result["status"] == "PASS", result["errors"]
    assert result["mapped_values"] > 0


def test_v2_detects_semantic_opcode_mutation() -> None:
    stream, _model, _verification = build_stream(SOURCE)
    lines = stream.splitlines()
    changed = False
    for index, line in enumerate(lines):
        if line.startswith("I "):
            fields = line.split()
            fields[5] = "25" if fields[5] != "25" else "5"
            lines[index] = " ".join(fields)
            changed = True
            break
    assert changed
    mutated = "\n".join(lines) + "\n"
    result = verify_conformance(SOURCE, mutated)
    assert result["status"] == "FAIL"
    assert any("semantic shape mismatch" in error for error in result["errors"])


def test_v2_internal_verifier_rejects_incomplete_mask() -> None:
    stream, _model, _verification = build_stream(SOURCE)
    mutated = stream.replace(f"Z {COMPLETE_MASK}\n", "Z 0\n")
    parsed = parse_stream(mutated)
    result = verify_stream(parsed)
    assert result["status"] == "BLOCKED"
    assert result["complete"] is False


def test_v2_branch_targets_are_numeric_and_resolved() -> None:
    stream, _model, verification = build_stream(SOURCE)
    assert verification["status"] == "PASS"
    parsed = parse_stream(stream)
    branch_records = [
        record["fields"]
        for record in parsed["records"]
        if record["tag"] == "T" and record["fields"][1] == 3
    ]
    assert branch_records
    for fields in branch_records:
        assert fields[2] >= 0
        assert fields[3] >= 0
        assert fields[4] >= 0
        assert fields[5] >= 0
