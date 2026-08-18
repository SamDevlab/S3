from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.semantic import ValueLayoutKind


def test_owned_record_with_dynamic_field_round_trips_o0_o1() -> None:
    source = (
        "record User:\n"
        "    name: text\n"
        "    count: tryte\n"
        "fn identity(value: User) -> User:\n"
        "    return value\n"
        "fn main() -> i64:\n"
        '    user: User = User(name=text_from_static("hello"), count=7)\n'
        "    result: User = identity(user)\n"
        "    return text_len(&result.name)\n"
    )

    assert run_source(source, optimization="O0") == 5
    assert run_source(source, optimization="O1") == 5
    compilation = compile_source(source, optimization="O0")
    identity = compilation.ir.functions[0]
    assert [parameter.name for parameter in identity.parameters] == [
        "value__name",
        "value__count",
    ]
    assert [cell.path for cell in compilation.semantic_model.record_leaves("User")] == [
        ("name",),
        ("count",),
    ]


def test_dynamic_owned_array_of_records_preserves_flattened_order() -> None:
    source = (
        "record User:\n"
        "    name: text\n"
        "fn first(values: User[2]) -> i64:\n"
        "    return text_len(&values[1].name)\n"
        "fn main() -> i64:\n"
        '    values: User[2] = [User(name=text_from_static("a")), User(name=text_from_static("second"))]\n'
        "    return first(values)\n"
    )

    assert run_source(source, optimization="O0") == 6
    assert run_source(source, optimization="O1") == 6
    compilation = compile_source(source, optimization="O0")
    first = compilation.ir.functions[0]
    assert [parameter.name for parameter in first.parameters] == [
        "values__index0__name",
        "values__index1__name",
    ]
    layout = compilation.semantic_model.fixed_value_layout(
        ast.ArrayType(
            ast.NominalType("User", compilation.ast.location),
            2,
            compilation.ast.location,
        )
    )
    assert layout.kind is ValueLayoutKind.FIXED_ARRAY
    assert [cell.path for cell in layout.cells] == [
        ("index0", "name"),
        ("index1", "name"),
    ]


def test_enum_dynamic_payload_and_inactive_dynamic_slot_are_lowered() -> None:
    source = (
        "enum Result:\n"
        "    Ok(name: text)\n"
        "    Empty\n"
        "fn inspect(result: Result) -> i64:\n"
        "    match result:\n"
        "        Result.Ok(name):\n"
        "            return text_len(&name)\n"
        "        Result.Empty:\n"
        "            return 0\n"
        "fn main() -> i64:\n"
        '    result: Result = Result.Ok(name=text_from_static("ready"))\n'
        "    return inspect(result)\n"
    )

    assert run_source(source, optimization="O0") == 5
    assert run_source(source, optimization="O1") == 5
    compilation = compile_source(source, optimization="O0")
    layout = compilation.semantic_model.enum_layout("Result")
    assert layout.slot_types == (ast.TypeName.TRYTE, ast.TypeName.TEXT)


def test_mutable_owned_record_field_replacement_is_a_whole_value_update() -> None:
    source = (
        "record User:\n"
        "    name: text\n"
        "    count: tryte\n"
        "fn main() -> i64:\n"
        '    mut user: User = User(name=text_from_static("old"), count=1)\n'
        '    user.name = text_from_static("updated")\n'
        "    return text_len(&user.name)\n"
    )

    assert run_source(source, optimization="O0") == 7
    assert run_source(source, optimization="O1") == 7


def test_whole_owned_aggregate_move_and_borrow_rules_remain_enforced() -> None:
    moved = (
        "record User:\n"
        "    name: text\n"
        "fn main() -> i64:\n"
        '    user: User = User(name=text_from_static("x"))\n'
        "    moved: User = user\n"
        "    return text_len(&user.name)\n"
    )
    with pytest.raises(SemanticError) as error:
        compile_source(moved)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_USE_AFTER_MOVE

    borrowed_move = (
        "record User:\n"
        "    name: text\n"
        "fn main() -> i64:\n"
        '    user: User = User(name=text_from_static("x"))\n'
        "    view: &text = &user.name\n"
        "    moved: User = user\n"
        "    return text_len(view)\n"
    )
    with pytest.raises(SemanticError) as error:
        compile_source(borrowed_move)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_BORROWED_OWNER
