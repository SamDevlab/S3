from __future__ import annotations

from tools.stage1_source_binding_reference import build_binding_reference


SOURCE = """\
fn choose(a: i64, b: i64) -> i64:
    base: i64 = a
    mut total: i64 = base + b
    while total <=> 10:
        inner: i64 = total
        total = inner + 1
    return total
"""


def test_binding_reference_preserves_parameter_and_local_identity() -> None:
    reference = build_binding_reference(SOURCE)
    rows = reference["bindings"]

    assert reference["physical_storage_is_source_identity"] is False
    assert [(row["kind"], row["name"]) for row in rows] == [
        ("parameter", "a"),
        ("parameter", "b"),
        ("local", "base"),
        ("local", "total"),
        ("local", "inner"),
    ]
    assert [row["binding_id"] for row in rows] == list(range(len(rows)))


def test_binding_reference_preserves_mutability_and_declared_types() -> None:
    reference = build_binding_reference(SOURCE)
    by_name = {row["name"]: row for row in reference["bindings"]}

    assert by_name["a"]["mutable"] is False
    assert by_name["b"]["mutable"] is False
    assert by_name["base"]["mutable"] is False
    assert by_name["total"]["mutable"] is True
    assert by_name["inner"]["mutable"] is False
    assert {row["declared_type"] for row in reference["bindings"]} == {"i64"}


def test_nested_local_scope_is_distinct_from_function_root_scope() -> None:
    reference = build_binding_reference(SOURCE)
    by_name = {row["name"]: row for row in reference["bindings"]}

    assert by_name["base"]["scope_path"] == []
    assert by_name["total"]["scope_path"] == []
    assert by_name["inner"]["scope_path"] != []
