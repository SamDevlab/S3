from __future__ import annotations

from pathlib import Path

from tools.stage1_representability import analyze_stage1


def test_stage1_representability_inventory_covers_each_function_and_is_deterministic() -> None:
    source_path = Path(__file__).parents[1] / "selfhost/compiler/stage1_compiler_v1.s3"
    source = source_path.read_text(encoding="utf-8")

    first = analyze_stage1(source)
    second = analyze_stage1(source)

    assert first == second
    assert first["functions_total"] == 50
    assert first["functions_representable"] == 0
    assert first["source_bytes"] == 139740
    assert first["source_sha256"] == (
        "894a76a5c206b8e86b3149483b4bc2ad6904a4f6810aac62d1e235c1fd46a44c"
    )
    assert len(first["functions"]) == 50
    assert all(item["representable"] is False for item in first["functions"])
    assert any(item["body_supported_by_v1"] is True for item in first["functions"])

    target = next(
        item
        for item in first["functions"]
        if item["name"] == "stage1_emission_value_count"
    )
    assert target["signature"] == "(&vector<i64>) -> i64"
    assert target["uses_references"] is True
    assert target["uses_vectors"] is True
    assert target["calls"] == ["vector_get"]
    assert target["primary_blocker"] == "unsupported_reference_signature"
    assert target["representable_with_reference_vector_get_subset"] is True

    projection = first["capability_projection"]
    assert projection["functions_unlocked_by_typed_ir_only"] == 0
    assert projection["functions_unlocked_by_references_only"] == 0
    assert projection["functions_unlocked_by_vectors_only"] == 0
    assert projection["functions_unlocked_by_references_plus_vectors_and_i64_vector_get"] == 3
    assert projection["reference_vector_get_candidate_functions"] == [
        "stage1_emission_value_count",
        "stage1_emission_instruction_count",
        "stage1_emission_value_id",
    ]
    assert projection["projection_scope"].endswith(
        "excludes dependency closure and runtime/backend gates"
    )


def test_stage1_representability_inventory_builds_local_call_edges() -> None:
    source = """\
fn helper(value: i64) -> i64:
    return value

fn main() -> i64:
    return helper(4)
"""
    matrix = analyze_stage1(source)
    helper, main = matrix["functions"]

    assert helper["local_calls"] == []
    assert main["local_calls"] == ["helper"]
    assert main["uses_nested_calls"] is False
    assert matrix["functions_total"] == 2
    assert helper["representable"] is True
    assert main["representable"] is True
    assert main["dependency_closed"] is True


def test_stage1_representability_does_not_count_signature_or_body_parsing_alone() -> None:
    source = """\
fn indexed(view: &vector<i64>) -> i64:
    return vector_get<i64>(view, 0)
"""
    function, = analyze_stage1(source)["functions"]

    assert function["signature_supported_by_v1"] is False
    assert function["body_supported_by_v1"] is False
    assert function["representable"] is False
    assert function["representable_with_reference_vector_get_subset"] is True


def test_stage1_representability_rejects_unimplemented_scalar_body_operations() -> None:
    source = """\
fn subtract(value: i64) -> i64:
    return value - 1
"""
    function, = analyze_stage1(source)["functions"]

    assert function["signature_supported_by_v1"] is True
    assert function["representable"] is False
    assert function["primary_blocker"] == "unsupported_binary_operator"
