from __future__ import annotations

from pathlib import Path

from bootstrap.s3.pipeline import compile_source
from tools.stage1_source_binding_reference import build_binding_reference
from tools.patch_stage1_semantic_port_v2 import (
    BINDING_CAPACITY,
    DEFAULT_SOURCE,
    FUNCTION_CAPACITY,
    PARAMETER_CAPACITY,
    PATCH_MARKER,
    SCOPE_CAPACITY,
    apply_patch,
)


PASS1_BINDING_SOURCE = """\
foreign fn host(value: i64) -> i64
fn many(first: i64, second: i64) -> i64:
    mut result: i64 = first + second
    return host(result)
fn scoped(seed: i64) -> i64:
    mut value: i64 = seed
    while value < 3:
        mut nested: i64 = value
        match nested <=> 0:
            -1:
                mut value: i64 = nested
                discard value
            0:
                discard nested
            1:
                discard nested
        value += 1
    return value
fn looped() -> tryte:
    mut total: tryte = 0
    for item: tryte in range(3):
        total += item
    return total
fn main() -> i64:
    return many(1, 2)
"""


def test_pass1_transform_is_deterministic_and_idempotent() -> None:
    source = DEFAULT_SOURCE.read_text(encoding="utf-8")

    candidate = apply_patch(source)

    assert source == DEFAULT_SOURCE.read_text(encoding="utf-8")
    assert candidate != source
    assert candidate.startswith(PATCH_MARKER + "\n")
    assert candidate.count(PATCH_MARKER) == 1
    assert apply_patch(source) == candidate
    assert apply_patch(candidate) == candidate


def test_pass1_tables_have_explicit_bounded_capacities() -> None:
    source = DEFAULT_SOURCE.read_text(encoding="utf-8")
    candidate = apply_patch(source)

    assert f"mut semantic_v2_function_kind: tryte[{FUNCTION_CAPACITY}]" in candidate
    assert (
        f"mut semantic_v2_parameter_function: i64[{PARAMETER_CAPACITY}]"
        in candidate
    )
    assert f"mut semantic_v2_binding_function: i64[{BINDING_CAPACITY}]" in candidate
    assert (
        f"mut semantic_v2_scope_indent: i64[{SCOPE_CAPACITY}]" in candidate
    )
    assert "semantic_v2_function_param_count[function_count] = 0" in candidate
    assert "semantic_v2_binding_count < 256" in candidate
    assert "semantic_v2_scope_depth < 32" in candidate

    # The v2 Pass1 tables are bounded metadata, not a replacement for the
    # forbidden fixed 365-entry semantic value namespace.
    assert "semantic_v2_function_kind: tryte[365]" not in candidate
    assert "semantic_v2_parameter_function: i64[365]" not in candidate
    assert "semantic_v2_binding_function: i64[365]" not in candidate


def test_pass1_preserves_exact_spans_and_separates_logical_storage_ids() -> None:
    source = DEFAULT_SOURCE.read_text(encoding="utf-8")
    candidate = apply_patch(source)

    assert "semantic_v2_token_start[slot] = actual_start" in candidate
    assert "semantic_v2_function_name_start[function_count] = actual_start" in candidate
    assert "semantic_v2_parameter_name_slot = slot - 1" in candidate
    assert "semantic_v2_parameter_previous_slot = semantic_v2_parameter_name_slot" in candidate
    assert "semantic_v2_parameter_name_start[parameter_count] = semantic_v2_token_start" in candidate
    assert "semantic_v2_binding_name_start[semantic_v2_binding_count] = local_capture_name_start" in candidate
    assert "semantic_v2_parameter_value_id[parameter_count] = semantic_v2_next_value_id" in candidate
    assert "semantic_v2_binding_value_id[semantic_v2_binding_count] = semantic_v2_next_value_id" in candidate
    assert "semantic_v2_binding_storage[semantic_v2_binding_count] = semantic_v2_next_storage_id" in candidate
    assert "semantic_v2_next_value_id += 1" in candidate
    assert "semantic_v2_next_storage_id += 1" in candidate


def test_pass1_records_function_kind_signatures_and_lexical_scope_hooks() -> None:
    source = DEFAULT_SOURCE.read_text(encoding="utf-8")
    candidate = apply_patch(source)

    assert "semantic_v2_function_kind[function_count] = 1" in candidate
    assert "semantic_v2_function_kind[function_count] = 2" in candidate
    assert "semantic_v2_function_return_type[current_function] = value" in candidate
    assert "semantic_v2_function_result_count[current_function] = 1" in candidate
    assert "semantic_v2_scope_ids[semantic_v2_scope_depth] = semantic_v2_next_scope_id" in candidate
    assert "semantic_v2_scope_id = semantic_v2_next_scope_id" in candidate
    assert "semantic_v2_binding_scope[semantic_v2_binding_count] = local_capture_scope" in candidate
    assert "semantic_v2_loop_capture_state = 1" in candidate
    assert "semantic_v2_loop_capture_state = 4" in candidate
    assert "semantic_v2_loop_type = value" in candidate


def test_candidate_output_path_is_separate_from_canonical_source() -> None:
    assert Path(DEFAULT_SOURCE).name == "s3c_stage1.s3"
    assert DEFAULT_SOURCE != Path(".artifacts/s3c_stage1_semantic_v2.s3")


def test_pass1_reference_corpus_covers_function_and_binding_shapes() -> None:
    compilation = compile_source(PASS1_BINDING_SOURCE)
    reference = build_binding_reference(PASS1_BINDING_SOURCE)

    assert [function.name for function in compilation.ast.foreign_functions] == ["host"]
    assert [function.name for function in compilation.ast.functions] == [
        "many",
        "scoped",
        "looped",
        "main",
    ]
    assert [len(function.parameters) for function in compilation.ast.functions] == [
        2,
        1,
        0,
        0,
    ]

    bindings = reference["bindings"]
    assert [(item["function"], item["kind"], item["name"]) for item in bindings] == [
        ("many", "parameter", "first"),
        ("many", "parameter", "second"),
        ("many", "local", "result"),
        ("scoped", "parameter", "seed"),
        ("scoped", "local", "value"),
        ("scoped", "local", "nested"),
        ("scoped", "local", "value"),
        ("looped", "local", "total"),
        ("looped", "loop_variable", "item"),
    ]
    assert bindings[2]["mutable"] is True
    assert bindings[6]["scope_path"] != bindings[4]["scope_path"]
    assert bindings[8]["mutable"] is False


def test_pass1_reference_corpus_preserves_local_array_metadata() -> None:
    source = (Path(__file__).parents[1] / "examples" / "static_array.s3").read_text(
        encoding="utf-8"
    )
    reference = build_binding_reference(source)

    assert reference["bindings"] == [
        {
            "binding_id": 0,
            "function_index": 0,
            "function": "main",
            "kind": "local",
            "name": "values",
            "declared_type": "array[4]<tryte>",
            "mutable": True,
            "scope_path": [],
            "statement_ordinal": 0,
            "source": {"offset": 24, "line": 2, "column": 5},
            "semantic_value_link": "TO_BE_RESOLVED_BY_STAGE1_LOWERING",
            "physical_storage_is_identity": False,
        }
    ]
