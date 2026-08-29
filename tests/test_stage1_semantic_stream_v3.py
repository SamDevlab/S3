from __future__ import annotations

import hashlib

from tools.stage1_semantic_stream_v3 import (
    BINDING_TARGET_CODES,
    build_model,
    build_model_bytes,
    build_stream,
    encode_model,
    parse_stream,
    verify_stream,
)
from tools.verify_stage1_semantic_conformance_v3 import verify_conformance


def test_raw_crlf_source_identity_is_not_normalized() -> None:
    raw = b"fn main() -> i64:\r\n    return 0\r\n"
    model = build_model_bytes(raw)
    assert model["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert model["source_bytes"] == len(raw)
    assert model["source_newline_policy"] == "RAW_BYTES_PRESERVED"
    assert model["functions"][0]["name_start"] == raw.index(b"main")


def test_discard_literal_remains_a_real_const_value_at_o0() -> None:
    source = """\
fn main() -> i64:
    discard 0
    return 0
"""
    model = build_model(source)
    zeros = [
        row
        for row in model["instructions"]
        if row["opcode"] == "const" and row.get("immediate") == 0
    ]
    assert len(zeros) >= 2
    assert len({row["instruction_id"] for row in zeros}) == len(zeros)


def test_immutable_local_binding_targets_existing_value() -> None:
    source = """\
fn main() -> i64:
    value: i64 = 1
    return value
"""
    model = build_model(source)
    local = next(row for row in model["bindings"] if row["kind"] == "local")
    assert local["target_kind"] == "value"
    value_ids = {row["value_id"] for row in model["values"]}
    assert local["target_id"] in value_ids


def test_mutable_local_binding_targets_existing_storage() -> None:
    source = """\
fn main() -> i64:
    mut value: i64 = 1
    value = value + 1
    return value
"""
    model = build_model(source)
    local = next(row for row in model["bindings"] if row["kind"] == "local")
    assert local["target_kind"] == "storage"
    storage = {
        (row["function_id"], row["storage_id"]): row
        for row in model["storage"]
    }
    row = storage[(local["function_id"], local["target_id"])]
    assert row["mutable"] is True
    assert row["length"] == 1


def test_large_i64_immediate_is_preserved_exactly() -> None:
    source = """\
fn main() -> i64:
    return 1000000000000
"""
    model = build_model(source)
    assert any(
        row["opcode"] == "const" and row.get("immediate") == 1_000_000_000_000
        for row in model["instructions"]
    )


def test_self_stream_passes_semantic_v3_conformance() -> None:
    source = """\
fn add(a: i64, b: i64) -> i64:
    return a + b

fn main() -> i64:
    mut value: i64 = add(20, 22)
    while value < 45:
        value += 1
    return value
"""
    stream, _model, verification = build_stream(source)
    assert verification["status"] == "PASS"
    result = verify_conformance(source, stream)
    assert result["status"] == "PASS"
    assert result["mapped_values"] == result["expected"]["values"]
    assert result["mapped_storage"] == result["expected"]["storage"]


def test_binding_to_nonexistent_storage_fails_closed() -> None:
    source = """\
fn main() -> i64:
    mut value: i64 = 1
    return value
"""
    model = build_model(source)
    stream = encode_model(model)
    parsed = parse_stream(stream)
    records = [dict(row) for row in parsed["records"]]
    for record in records:
        if record["tag"] == "D" and record["fields"][7] == BINDING_TARGET_CODES["storage"]:
            record["fields"] = list(record["fields"])
            record["fields"][8] += 999
            break
    mutated = "S3IR2 3\n" + "\n".join(
        f"{record['tag']} " + " ".join(str(value) for value in record["fields"])
        for record in records
    ) + "\n"
    assert verify_stream(parse_stream(mutated))["status"] == "BLOCKED"


def test_storage_shape_mutation_is_rejected_by_conformance() -> None:
    source = """\
fn main() -> i64:
    mut value: i64 = 1
    return value
"""
    stream, _model, _verification = build_stream(source)
    lines = stream.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("M "):
            fields = line.split()
            fields[4] = str(int(fields[4]) + 1)
            lines[index] = " ".join(fields)
            break
    mutated = "\n".join(lines) + "\n"
    result = verify_conformance(source, mutated)
    assert result["status"] == "FAIL"
    assert any(
        "storage" in error or "binding/storage" in error
        for error in result["errors"]
    )
