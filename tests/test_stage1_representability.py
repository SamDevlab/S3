from __future__ import annotations

import hashlib
import json
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


def test_stage1_v2_analyzer_reports_proven_canonical_self_compile_slice() -> None:
    source_path = Path(__file__).parents[1] / "selfhost/compiler/stage1_compiler_v1.s3"
    source = source_path.read_text(encoding="utf-8")

    matrix = analyze_stage1(source, compiler_version="v2")
    serialized = json.dumps(matrix, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    repeated = json.dumps(
        analyze_stage1(source, compiler_version="v2"),
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ) + "\n"

    assert serialized == repeated
    assert hashlib.sha256(serialized.encode("ascii")).hexdigest() == hashlib.sha256(
        repeated.encode("ascii")
    ).hexdigest()
    assert matrix["functions_total"] == 50
    assert matrix["functions_signature_supported"] == 14
    assert matrix["functions_body_representable"] == 5
    assert matrix["functions_representable"] == 5
    assert matrix["functions_dependency_closed"] == 5
    assert matrix["functions_self_compile_proven"] == 5
    proven = {item["name"] for item in matrix["functions"] if item["self_compile_pass"]}
    assert proven == {
        "stage1_emission_value_count",
        "stage1_emission_instruction_count",
        "stage1_emission_value_id",
        "stage1_emission_operand_id",
        "stage1_emission_instruction_field",
    }
    assert all(
        item["self_compile_tested"] is True
        for item in matrix["functions"]
        if item["self_compile_pass"]
    )


def test_stage1_v2_analyzer_identifies_output_chunk_control_and_storage_blockers() -> None:
    source_path = Path(__file__).parents[1] / "selfhost/compiler/stage1_compiler_v1.s3"
    source = source_path.read_text(encoding="utf-8")
    matrix = analyze_stage1(source, compiler_version="v2")
    target = next(item for item in matrix["functions"] if item["name"] == "stage1_output_chunk")

    assert target["signature_supported"] is True
    assert target["representable"] is False
    assert "WhileStatement" in target["unsupported_syntax"]
    assert "SwitchStatement" in target["unsupported_syntax"]
    assert "mutable_assignment_in_control_flow" in target["unsupported_operations"]
    assert "binary_<" not in target["unsupported_operations"]
    assert "binary_==" not in target["unsupported_operations"]
    assert target["calls"] == ["vector_get", "vector_len"]
    assert target["unsupported_callees"] == []


def test_stage1_v2_analyzer_models_typed_comparisons_as_trit_results() -> None:
    source = """\
fn less(left: i64, right: i64) -> trit:
    return left < right

fn equal(left: i64, right: i64) -> trit:
    return left == right
"""
    less, equal = analyze_stage1(source, compiler_version="v2")["functions"]

    for function in (less, equal):
        assert function["signature_supported"] is True
        assert function["body_representable"] is True
        assert function["representable"] is True
        assert function["unsupported_operations"] == []


def test_stage1_v2_analyzer_rejects_comparisons_with_incompatible_types() -> None:
    source = """\
fn invalid(left: trit, right: i64) -> trit:
    return left < right
"""
    function, = analyze_stage1(source, compiler_version="v2")["functions"]

    assert function["signature_supported"] is True
    assert function["body_representable"] is False
    assert "binary_operand_type_mismatch" in function["unsupported_operations"]


def test_stage1_v2_analyzer_separates_signature_from_body_representability() -> None:
    source = """\
fn unsupported_parameter(view: &vector<f64>) -> i64:
    return 1
"""
    function, = analyze_stage1(source, compiler_version="v2")["functions"]

    assert function["signature_supported"] is False
    assert function["body_representable"] is True
    assert function["representable"] is False
    assert function["unsupported_signature_types"] == ["&vector<f64>"]


def test_stage1_v2_analyzer_counts_only_supported_straight_line_mutation() -> None:
    source = """\
fn update(value: i64) -> i64:
    mut current: i64 = value
    current = current + 1
    return current
"""
    function, = analyze_stage1(source, compiler_version="v2")["functions"]

    assert function["representable"] is True
    assert function["local_bindings"] == [
        {"name": "current", "type": "i64", "mutable": True}
    ]
    assert function["source_span"] == {"start_offset": 0, "end_offset": len(source)}
    assert function["primary_blocker"] is None
    assert function["secondary_blockers"] == []


def test_stage1_v2_analyzer_rejects_immutable_and_nested_mutation() -> None:
    immutable = """\
fn update(value: i64) -> i64:
    current: i64 = value
    current = current + 1
    return current
"""
    nested = """\
fn update(value: i64) -> i64:
    mut current: i64 = value
    while current < 4:
        current = current + 1
    return current
"""

    immutable_function, = analyze_stage1(immutable, compiler_version="v2")["functions"]
    nested_function, = analyze_stage1(nested, compiler_version="v2")["functions"]

    assert "assignment_to_immutable_binding:current" in immutable_function["unsupported_operations"]
    assert "WhileStatement" in nested_function["unsupported_syntax"]
    assert "mutable_assignment_in_control_flow" in nested_function["unsupported_operations"]
    assert not nested_function["representable"]
