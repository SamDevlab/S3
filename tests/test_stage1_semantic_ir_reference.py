from __future__ import annotations

from tools.stage1_semantic_ir_reference import build_reference


CALL_AND_BRANCH_SOURCE = """\
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


ARRAY_SOURCE = """\
fn main() -> i64:
    mut values: i64[3] = [10, 20, 30]
    values[1] = 25
    return values[1]
"""


def test_reference_closes_all_five_emitter_facing_lanes() -> None:
    reference = build_reference(CALL_AND_BRANCH_SOURCE)

    assert reference["status"] == "PASS"
    assert reference["physical_storage_is_semantic_identity"] is False
    assert reference["completeness"] == {
        "typed_value_definitions": True,
        "instruction_def_use": True,
        "call_dataflow": True,
        "complete_terminators": True,
        "canonical_serialized_ir": True,
    }
    assert reference["errors"] == []


def test_logical_value_ids_are_unique_typed_and_definition_backed() -> None:
    reference = build_reference(CALL_AND_BRANCH_SOURCE)
    values = reference["lanes"]["typed_values"]

    ids = [row["value_id"] for row in values]
    assert ids == list(range(len(ids)))
    assert len(ids) == len(set(ids))
    assert all(row["type"] in {"trit", "tryte", "i64", "f64", "string", "bytes", "text", "vector", "reference"} for row in values)
    assert all(row["definition"]["kind"] != "unresolved" for row in values)

    parameters = [row for row in values if row["definition"]["kind"] == "parameter"]
    assert {(row["function"], row["definition"]["parameter_name"]) for row in parameters} >= {
        ("add", "a"),
        ("add", "b"),
    }


def test_instruction_operands_and_results_resolve_to_semantic_value_ids() -> None:
    reference = build_reference(CALL_AND_BRANCH_SOURCE)
    values = {row["value_id"] for row in reference["lanes"]["typed_values"]}

    for instruction in reference["lanes"]["instructions"]:
        assert set(instruction["operand_value_ids"]) <= values
        assert set(instruction["result_value_ids"]) <= values


def test_call_lane_preserves_ordered_arguments_results_and_callee_identity() -> None:
    reference = build_reference(CALL_AND_BRANCH_SOURCE)
    calls = [row for row in reference["lanes"]["calls"] if row["callee"] == "add"]

    assert len(calls) == 1
    call = calls[0]
    assert call["callee_kind"] == "internal"
    assert call["callee_resolves_in_module"] is True
    assert len(call["argument_value_ids"]) == 2
    assert len(call["result_value_ids"]) == 1


def test_terminator_lane_preserves_branch3_condition_targets_and_returns() -> None:
    reference = build_reference(CALL_AND_BRANCH_SOURCE)
    terminators = reference["lanes"]["terminators"]

    branch3 = [row for row in terminators if row["kind"] == "branch3"]
    returns = [row for row in terminators if row["kind"] == "return"]
    assert branch3
    assert returns
    assert all(row["condition_value_id"] is not None for row in branch3)
    assert all(len(row["targets"]) == 3 for row in branch3)
    assert all("return_value_ids" in row for row in returns)


def test_memory_storage_is_preserved_without_aliasing_it_to_semantic_value_ids() -> None:
    reference = build_reference(ARRAY_SOURCE)
    storage = reference["lanes"]["storage_objects"]

    assert storage
    assert any(row["mutable"] is True for row in storage)
    assert all(row["identity_status"] == "IR_MEMORY_IDENTITY_ONLY" for row in storage)
    assert all("value_id" not in row for row in storage)


def test_canonical_serialization_is_deterministic() -> None:
    first = build_reference(CALL_AND_BRANCH_SOURCE)
    second = build_reference(CALL_AND_BRANCH_SOURCE)

    assert first["serialization"]["format"] == "S3IR2-REFERENCE"
    assert first["serialization"]["canonical_json"] is True
    assert first["serialization"]["sha256"] == second["serialization"]["sha256"]
    assert first["serialization"]["bytes"] == second["serialization"]["bytes"]
