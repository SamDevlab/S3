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
    # The token newline scanner is representable through its explicit external
    # helper contracts; self-compilation remains gated by execution evidence.
    assert matrix["functions_signature_supported"] == 24
    assert matrix["functions_body_representable"] == 23
    assert matrix["functions_representable"] == 23
    assert matrix["functions_dependency_closed"] == 23
    assert matrix["functions_self_compile_proven"] == 17
    assert matrix["functions_selfhosted_compiler_behavior"] == 10
    assert "vector<i64>" in matrix["capabilities"]["local_types"]
    assert "vector_new<i64>" in matrix["capabilities"]["external_calls"]
    assert "i64_vector_get" in matrix["capabilities"]["external_calls"]
    assert "i64_vector_len" in matrix["capabilities"]["external_calls"]
    assert matrix["capabilities"]["program_function_capacity"] == 16
    assert matrix["capabilities"]["program_block_capacity"] == 64
    assert matrix["capabilities"]["max_source_bytes"] == 4096
    assert matrix["capabilities"]["max_token_count"] == 1024
    proven = {item["name"] for item in matrix["functions"] if item["self_compile_pass"]}
    assert proven == {
        "stage1_source_spans_equal",
        "stage1_find_symbol_value",
        "stage1_parameter_name_seen",
        "stage1_parameter_names_unique",
        "stage1_emission_value_count",
        "stage1_emission_instruction_count",
        "stage1_emission_value_id",
        "stage1_emission_operand_id",
        "stage1_emission_instruction_field",
        "stage1_emit_decimal",
        "stage1_emit_register",
        "stage1_source_name_is_main",
        "stage1_find_function_id_by_source_name",
        "stage1_emit_ir_function_name",
        "stage1_emit_ir_callee_name",
        "stage1_skip_body_newlines",
        "stage1_output_chunk",
    }
    assert all(
        item["self_compile_tested"] is True
        for item in matrix["functions"]
        if item["self_compile_pass"]
    )

    behavior = {
        item["name"]: item["compiler_behavior_category"]
        for item in matrix["functions"]
        if item["selfhosted_compiler_behavior"]
    }
    assert behavior == {
        "stage1_find_symbol_value": "symbol_resolution",
        "stage1_parameter_names_unique": "parameter_validation",
        "stage1_find_function_id_by_source_name": "symbol_resolution",
        "stage1_emit_ir_function_name": "assembly_emission",
        "stage1_emit_ir_callee_name": "assembly_emission",
        "stage1_skip_body_newlines": "token_scanning",
        "stage1_output_chunk": "assembly_emission",
        "stage1_emit_decimal": "assembly_emission",
        "stage1_emit_register": "assembly_emission",
        "stage1_source_name_is_main": "entry_point_classification",
    }
    large_selfhost_targets = {
        item["name"]: item["source_bytes"]
        for item in matrix["functions"]
        if item["name"]
        in {"stage1_literal_bytes", "stage1_emit_single_main_program"}
    }
    assert large_selfhost_targets == {
        "stage1_literal_bytes": 19082,
        "stage1_emit_single_main_program": 10598,
    }
    assert all(
        item["function_source_within_byte_limit"] is False
        for item in matrix["functions"]
        if item["name"] in large_selfhost_targets
    )

    newly_closed = {
        item["name"]
        for item in matrix["functions"]
        if item["name"]
        in {
            "stage1_find_function_id_by_source_name",
            "stage1_emit_ir_function_name",
            "stage1_emit_ir_callee_name",
            "stage1_source_spans_equal",
            "stage1_parameter_name_seen",
            "stage1_parameter_names_unique",
            "stage1_source_name_is_main",
            "stage1_emit_decimal",
            "stage1_emit_register",
            "stage1_emit_single_main_program",
        }
        and item["dependency_closed"]
    }
    assert newly_closed == {
        "stage1_find_function_id_by_source_name",
        "stage1_emit_ir_function_name",
        "stage1_emit_ir_callee_name",
        "stage1_source_spans_equal",
        "stage1_parameter_name_seen",
        "stage1_parameter_names_unique",
        "stage1_source_name_is_main",
        "stage1_emit_decimal",
        "stage1_emit_register",
        "stage1_emit_single_main_program",
    }

    decimal = next(
        item for item in matrix["functions"]
        if item["name"] == "stage1_emit_decimal"
    )
    assert decimal["signature_supported"] is True
    assert decimal["body_representable"] is True
    assert decimal["dependency_closed"] is True
    assert decimal["unsupported_operations"] == []
    assert decimal["unsupported_types"] == []
    assert decimal["unsupported_callees"] == []


def test_stage1_v2_analyzer_closes_canonical_i64_vector_symbol_lookup() -> None:
    source = (
        Path(__file__).parents[1] / "selfhost/compiler/stage1_compiler_v1.s3"
    ).read_text(encoding="utf-8")
    matrix = analyze_stage1(source, compiler_version="v2")
    function = next(
        item for item in matrix["functions"]
        if item["name"] == "stage1_find_function_id_by_source_name"
    )

    assert function["signature_supported"] is True
    assert function["body_representable"] is True
    assert function["dependency_closed"] is True
    assert function["self_compile_pass"] is True
    assert function["selfhosted_compiler_behavior"] is True
    assert function["compiler_behavior_category"] == "symbol_resolution"
    assert function["self_compile_evidence"] == (
        "tests/test_s3_1_13_stage1_compiler.py::"
        "test_stage1_v2_executes_canonical_function_symbol_lookup_natively"
    )
    assert function["unsupported_callees"] == []
    assert function["unsupported_operations"] == []


def test_stage1_v2_analyzer_closes_canonical_ir_name_emission_cluster() -> None:
    source = (
        Path(__file__).parents[1] / "selfhost/compiler/stage1_compiler_v1.s3"
    ).read_text(encoding="utf-8")
    matrix = analyze_stage1(source, compiler_version="v2")
    functions = {
        item["name"]: item
        for item in matrix["functions"]
        if item["name"] in {
            "stage1_emit_ir_function_name",
            "stage1_emit_ir_callee_name",
        }
    }

    assert set(functions) == {
        "stage1_emit_ir_function_name",
        "stage1_emit_ir_callee_name",
    }
    assert functions["stage1_emit_ir_function_name"]["dependency_closed"] is True
    assert functions["stage1_emit_ir_callee_name"]["dependency_closed"] is True
    assert functions["stage1_emit_ir_callee_name"]["local_calls"] == [
        "stage1_emit_ir_function_name"
    ]
    assert all(
        item["compiler_behavior_category"] == "assembly_emission"
        for item in functions.values()
    )


def test_stage1_v2_analyzer_validates_i64_vector_intrinsic_signatures() -> None:
    valid = """\
fn lookup(view: &vector<i64>, index: i64) -> i64:
    return i64_vector_get(view, index)
fn count(view: &vector<i64>) -> i64:
    return i64_vector_len(view)
"""
    wrong_type_arguments = """\
fn invalid(view: &vector<i64>) -> i64:
    return i64_vector_len<i64>(view)
"""
    wrong_argument_shape = """\
fn invalid(view: &vector<i64>, index: trit) -> i64:
    return i64_vector_get(view, index)
"""

    valid_matrix = analyze_stage1(valid, compiler_version="v2")
    assert all(item["body_representable"] for item in valid_matrix["functions"])

    typed, = analyze_stage1(
        wrong_type_arguments, compiler_version="v2"
    )["functions"]
    assert "i64_vector_len:does-not-take-type-arguments" in typed["unsupported_types"]
    assert typed["body_representable"] is False

    shaped, = analyze_stage1(
        wrong_argument_shape, compiler_version="v2"
    )["functions"]
    assert "i64_vector_get:argument-shape" in shaped["unsupported_operations"]
    assert shaped["body_representable"] is False


def test_stage1_v2_analyzer_models_token_newline_scanner_dependencies() -> None:
    source = (
        Path(__file__).parents[1] / "selfhost/compiler/stage1_compiler_v1.s3"
    ).read_text(encoding="utf-8")
    matrix = analyze_stage1(source, compiler_version="v2")
    function = next(
        item for item in matrix["functions"]
        if item["name"] == "stage1_skip_body_newlines"
    )

    assert function["signature_supported"] is True
    assert function["body_representable"] is True
    assert function["dependency_closed"] is True
    assert function["self_compile_pass"] is True
    assert function["selfhosted_compiler_behavior"] is True
    assert function["compiler_behavior_category"] == "token_scanning"
    assert function["self_compile_evidence"] == (
        "tests/test_s3_1_13_stage1_compiler.py::"
        "test_stage1_v2_emits_token_newline_scanner_for_native_execution"
    )
    assert set(function["external_dependencies"]) >= {
        "generic_token_count",
        "generic_token_kind",
    }
    assert function["unsupported_callees"] == []
    assert function["unsupported_operations"] == []


def test_stage1_v2_analyzer_recognizes_canonical_output_chunk_capabilities() -> None:
    source_path = Path(__file__).parents[1] / "selfhost/compiler/stage1_compiler_v1.s3"
    source = source_path.read_text(encoding="utf-8")
    matrix = analyze_stage1(source, compiler_version="v2")
    target = next(item for item in matrix["functions"] if item["name"] == "stage1_output_chunk")

    assert target["signature_supported"] is True
    assert target["body_syntax_supported"] is True
    assert target["operations_supported"] is True
    assert target["function_name"] == "stage1_output_chunk"
    assert target["body_representable"] is True
    assert target["representable"] is True
    assert target["dependency_closed"] is True
    assert target["dependencies_supported"] is True
    assert target["unsupported_syntax"] == []
    assert target["unsupported_operations"] == []
    assert target["calls"] == ["vector_get", "vector_len"]
    assert target["unsupported_callees"] == []


def test_stage1_v2_analyzer_models_typed_comparisons_as_trit_results() -> None:
    source = """\
fn less(left: i64, right: i64) -> trit:
    return left < right

fn equal(left: i64, right: i64) -> trit:
    return left == right
fn less_equal(left: i64, right: i64) -> trit:
    return left <= right
fn greater(left: i64, right: i64) -> trit:
    return left > right
fn greater_equal(left: i64, right: i64) -> trit:
    return left >= right
"""
    less, equal, less_equal, greater, greater_equal = analyze_stage1(
        source, compiler_version="v2"
    )["functions"]

    for function in (less, equal, less_equal, greater, greater_equal):
        assert function["signature_supported"] is True
        assert function["body_representable"] is True
        assert function["representable"] is True
        assert function["unsupported_operations"] == []


def test_stage1_v2_analyzer_models_local_vector_values_and_mutable_refs() -> None:
    source = """\
fn append_one(values: &mut vector<i64>) -> i64:
    return vector_push<i64>(values, 9)

fn build() -> i64:
    mut values: vector<i64> = vector_new<i64>(2)
    discard append_one(&mut values)
    return vector_get<i64>(&values, 0)
"""
    append_one, build = analyze_stage1(source, compiler_version="v2")["functions"]

    assert append_one["signature_supported"] is True
    assert append_one["body_representable"] is True
    assert append_one["dependency_closed"] is True
    assert build["signature_supported"] is True
    assert build["body_representable"] is True
    assert build["dependency_closed"] is True
    assert build["local_bindings"] == [
        {"name": "values", "type": "vector<i64>", "mutable": True}
    ]
    assert build["calls"] == ["append_one", "vector_get", "vector_new"]


def test_stage1_v2_analyzer_rejects_invalid_local_vector_references() -> None:
    immutable_binding = """\
fn invalid() -> i64:
    values: vector<i64> = vector_new<i64>(2)
    discard vector_push<i64>(&mut values, 9)
    return 0
"""
    immutable_reference_for_push = """\
fn invalid() -> i64:
    mut values: vector<i64> = vector_new<i64>(2)
    discard vector_push<i64>(&values, 9)
    return 0
"""
    wrong_vector_element = """\
fn invalid() -> i64:
    mut values: vector<i64> = vector_new<trit>(2)
    return 0
"""
    invalid_arity = """\
fn invalid() -> i64:
    mut values: vector<i64> = vector_new<i64>()
    return 0
"""

    immutable, = analyze_stage1(immutable_binding, compiler_version="v2")["functions"]
    immutable_ref, = analyze_stage1(
        immutable_reference_for_push, compiler_version="v2"
    )["functions"]
    wrong_element, = analyze_stage1(
        wrong_vector_element, compiler_version="v2"
    )["functions"]
    wrong_arity, = analyze_stage1(invalid_arity, compiler_version="v2")["functions"]

    assert "mutable_reference_requires_mutable_binding" in immutable["unsupported_operations"]
    assert "vector_push:argument-shape" in immutable_ref["unsupported_operations"]
    assert "vector_new:requires-i64-type-argument" in wrong_element["unsupported_types"]
    assert "vector_new:argument-shape" in wrong_arity["unsupported_operations"]
    assert all(
        not function["body_representable"]
        for function in (immutable, immutable_ref, wrong_element, wrong_arity)
    )


def test_stage1_v2_analyzer_reports_current_typed_cfg_and_difference_support() -> None:
    source = """\
fn subtract(left: i64, right: i64) -> i64:
    return left - right
"""
    matrix = analyze_stage1(source, compiler_version="v2")
    function, = matrix["functions"]
    capabilities = matrix["capabilities"]

    assert function["signature_supported"] is True
    assert function["body_representable"] is True
    assert function["unsupported_operations"] == []
    assert "i64_subtract_checked" in capabilities["expressions"]
    assert "typed_i64_relational_comparisons" in capabilities["expressions"]
    assert "ternary match lowered to a three-way CFG" in capabilities["control_flow"]
    assert "i64 mutable slots with typed TLOAD/TSTORE" in capabilities["mutation"]


def test_stage1_v2_analyzer_rejects_comparisons_with_incompatible_types() -> None:
    source = """\
fn invalid(left: trit, right: i64) -> trit:
    return left < right
"""
    function, = analyze_stage1(source, compiler_version="v2")["functions"]

    assert function["signature_supported"] is True
    assert function["body_representable"] is False
    assert "binary_operand_type_mismatch" in function["unsupported_operations"]


def test_stage1_v2_analyzer_models_discard_expression_and_local_call_edge() -> None:
    source = """\
fn effect() -> i64:
    return 7

fn main() -> i64:
    discard effect()
    return 42
"""
    effect, main = analyze_stage1(source, compiler_version="v2")["functions"]

    assert effect["representable"] is True
    assert main["representable"] is True
    assert main["dependency_closed"] is True
    assert main["calls"] == ["effect"]
    assert "DiscardStatement" not in main["unsupported_syntax"]


def test_stage1_v2_analyzer_models_discard_inside_supported_while_body() -> None:
    source = """\
fn effect() -> i64:
    return 7

fn main() -> i64:
    mut count: i64 = 0
    while count < 1:
        discard effect()
        count = count + 1
    return count
"""
    effect, main = analyze_stage1(source, compiler_version="v2")["functions"]

    assert effect["representable"] is True
    assert main["representable"] is True
    assert main["dependency_closed"] is True
    assert main["calls"] == ["effect"]
    assert "DiscardStatement" not in main["unsupported_syntax"]


def test_stage1_v2_analyzer_accepts_exhaustive_match_with_terminal_arms() -> None:
    source = """\
fn classify(flag: i64) -> i64:
    match flag < 0:
        -1:
            return 1
        0:
            return 2
        1:
            return 3
"""

    classify, = analyze_stage1(source, compiler_version="v2")["functions"]

    assert classify["representable"] is True
    assert classify["dependency_closed"] is True
    assert "missing_terminal_return" not in classify["unsupported_syntax"]


def test_stage1_v2_analyzer_keeps_fallthrough_match_arm_nonterminal() -> None:
    source = """\
fn classify(flag: i64) -> i64:
    match flag < 0:
        -1:
            return 1
        0:
            discard 2
        1:
            return 3
"""

    classify, = analyze_stage1(source, compiler_version="v2")["functions"]

    assert classify["representable"] is False
    assert "missing_terminal_return" in classify["unsupported_syntax"]


def test_stage1_v2_analyzer_models_mutable_vector_push_signature_and_effect() -> None:
    source = """\
fn append_value(output: &mut vector<i64>, value: i64) -> i64:
    discard vector_push<i64>(output, value)
    return 1

fn main() -> i64:
    return 0
"""
    append_value, main = analyze_stage1(source, compiler_version="v2")["functions"]

    assert append_value["signature_supported"] is True
    assert append_value["representable"] is True
    assert append_value["dependency_closed"] is True
    assert append_value["parameter_types"] == ["&mut vector<i64>", "i64"]
    assert append_value["calls"] == ["vector_push"]
    assert append_value["unsupported_callees"] == []
    assert append_value["unsupported_operations"] == []
    assert main["representable"] is True


def test_stage1_v2_analyzer_requires_mutable_i64_vector_for_push() -> None:
    immutable_reference = """\
fn invalid(output: &vector<i64>, value: i64) -> i64:
    discard vector_push<i64>(output, value)
    return 1
"""
    wrong_element_type = """\
fn invalid(output: &mut vector<i64>, value: i64) -> i64:
    discard vector_push<f64>(output, value)
    return 1
"""

    immutable, = analyze_stage1(
        immutable_reference, compiler_version="v2"
    )["functions"]
    wrong_type, = analyze_stage1(
        wrong_element_type, compiler_version="v2"
    )["functions"]

    assert "vector_push:argument-shape" in immutable["unsupported_operations"]
    assert immutable["representable"] is False
    assert "vector_push:requires-i64-type-argument" in wrong_type["unsupported_types"]
    assert wrong_type["representable"] is False


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


def test_stage1_v2_analyzer_supports_typed_vector_results_without_broad_casts() -> None:
    source = """\
fn make() -> vector<i64>:
    mut values: vector<i64> = vector_new<i64>(2)
    discard vector_push<i64>(&mut values, 17)
    return values

fn consume() -> i64:
    mut values: vector<i64> = make()
    return vector_len<i64>(&values)
"""
    make, consume = analyze_stage1(source, compiler_version="v2")["functions"]

    assert make["signature_supported"] is True
    assert make["body_representable"] is True
    assert make["dependency_closed"] is True
    assert consume["representable"] is True
    assert consume["local_calls"] == ["make"]

    wrong_return = """\
fn make() -> vector<i64>:
    return 17
"""
    wrong_element = """\
fn make() -> vector<f64>:
    return 17
"""
    invalid_return, = analyze_stage1(wrong_return, compiler_version="v2")["functions"]
    unsupported_element, = analyze_stage1(wrong_element, compiler_version="v2")["functions"]

    assert invalid_return["representable"] is False
    assert "return_type_mismatch" in invalid_return["unsupported_operations"]
    assert unsupported_element["signature_supported"] is False
    assert unsupported_element["unsupported_signature_types"] == ["vector<f64>"]


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
    loop = """\
fn update(value: i64) -> i64:
    mut current: i64 = value
    while current < 4:
        current = current + 1
    return current
"""
    nested_loop = """\
fn update(value: i64) -> i64:
    mut current: i64 = value
    while current < 4:
        while current < 2:
            current = current + 1
        current = current + 1
    return current
"""

    immutable_function, = analyze_stage1(immutable, compiler_version="v2")["functions"]
    loop_function, = analyze_stage1(loop, compiler_version="v2")["functions"]
    nested_function, = analyze_stage1(nested_loop, compiler_version="v2")["functions"]

    assert "assignment_to_immutable_binding:current" in immutable_function["unsupported_operations"]
    assert loop_function["representable"] is True
    assert "WhileStatement" not in nested_function["unsupported_syntax"]
    assert nested_function["unsupported_operations"] == []
    assert nested_function["representable"] is True


def test_stage1_v2_analyzer_rejects_i64_while_condition() -> None:
    source = """\
fn invalid() -> i64:
    mut ready: i64 = 1
    while ready:
        ready = 0
    return ready
"""
    function, = analyze_stage1(source, compiler_version="v2")["functions"]

    assert function["signature_supported"] is True
    assert "while_condition_type_mismatch" in function["unsupported_operations"]
    assert function["representable"] is False
