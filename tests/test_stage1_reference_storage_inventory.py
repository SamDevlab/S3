from __future__ import annotations

from pathlib import Path

import pytest

import tools.audit_stage1_reference_storage_inventory as oracle


pytestmark = pytest.mark.s3_fast


def _contract() -> dict[str, object]:
    return {"schema": "s3.selfhost.reference-storage-inventory-contract.v1"}


def _run_fixture(monkeypatch, source: str) -> dict[str, object]:
    payload = source.encode("utf-8")
    monkeypatch.setattr(
        oracle,
        "_canonical_source",
        lambda _path: (
            Path("/tmp/reference-storage-fixture.s3"),
            payload,
            {
                "schema": "s3.compiler.sources.v1",
                "source_count": 1,
                "total_bytes": len(payload),
            },
        ),
    )
    return oracle.audit(_contract(), Path("unused.json"))


def test_scalar_and_array_storage_are_classified_by_source_origin(monkeypatch) -> None:
    result = _run_fixture(
        monkeypatch,
        "fn main() -> tryte:\n"
        "    mut scalar: i64 = 1\n"
        "    mut values: i64[2] = [2, 5]\n"
        "    scalar = scalar + values[0]\n"
        "    values[1] = scalar\n"
        "    return to_tryte(values[1])\n",
    )
    assert result["status"] == "PASS_HOSTED_REFERENCE_STORAGE_INVENTORY"
    histogram = result["aggregate"]["memory_origin_kind_histogram"]
    assert histogram["local_scalar_declaration"] >= 1
    assert histogram["local_array_declaration"] >= 1
    assert result["aggregate"]["scalar_nonzero_or_unknown_index_access_count"] == 0
    assert result["aggregate"]["scalar_storage_access_count"] == result["aggregate"]["scalar_zero_index_access_count"]
    assert result["violations"] == []


def test_i64_array_index_is_preserved_as_valid_reference_ir_index(monkeypatch) -> None:
    result = _run_fixture(
        monkeypatch,
        "fn main() -> tryte:\n"
        "    mut values: i64[2] = [2, 5]\n"
        "    mut index: i64 = 1\n"
        "    values[index] = values[index] + 2\n"
        "    return to_tryte(values[index])\n",
    )
    assert result["status"] == "PASS_HOSTED_REFERENCE_STORAGE_INVENTORY"
    assert result["aggregate"]["i64_index_access_count"] > 0
    assert result["aggregate"]["array_access_count"] > 0
    assert not any(
        violation["kind"] == "INVALID_MEMORY_INDEX_TYPE"
        for violation in result["violations"]
    )


def test_array_of_length_one_is_not_misclassified_as_scalar(monkeypatch) -> None:
    result = _run_fixture(
        monkeypatch,
        "fn main() -> tryte:\n"
        "    mut one: i64[1] = [7]\n"
        "    return to_tryte(one[0])\n",
    )
    memories = result["memory_objects"]
    matching = [
        memory
        for memory in memories
        if memory["origin_kind"] == "local_array_declaration"
        and memory["length"] == 1
    ]
    assert matching
    assert not any(
        memory["origin_kind"] == "local_scalar_declaration"
        and memory["origin"] is not None
        and memory["origin"]["name"] == "one"
        for memory in memories
    )


def test_unmatched_memory_is_never_silently_counted_as_source_local(monkeypatch) -> None:
    result = _run_fixture(
        monkeypatch,
        "fn main() -> tryte:\n"
        "    return 1 < 2\n",
    )
    # Relational lowering uses internal memory for the ternary result.  It must
    # remain a lowering temporary rather than becoming a fake local merely
    # because its extent is one.
    assert result["aggregate"]["lowering_temporary_memory_count"] >= 1
    assert any(
        memory["origin_kind"] == "lowering_temporary_or_projection"
        for memory in result["memory_objects"]
    )


def test_reference_storage_oracle_never_authorizes_stage2(monkeypatch) -> None:
    result = _run_fixture(monkeypatch, "fn main() -> tryte:\n    return 7\n")
    assert result["native_evidence"] is False
    assert result["qualification"]["stage1_native_pass"] is False
    assert result["qualification"]["stage2_allowed"] is False
    assert result["qualification"]["full_self_hosting"] is False
