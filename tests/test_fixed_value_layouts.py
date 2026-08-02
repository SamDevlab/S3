from __future__ import annotations

from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import ReturnClass, ValueLayoutKind, analyze


def _analyze(source: str):
    program = parse(source, mode=SyntaxMode.V0_6)
    return program, analyze(program)


def test_scalar_and_static_text_value_layouts_are_single_cells() -> None:
    _, model = _analyze(
        "fn helper() -> string:\n"
        '    return "ok"\n'
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    tryte_layout = model.fixed_value_layout(ast.TypeName.TRYTE)
    assert tryte_layout.kind is ValueLayoutKind.SCALAR
    assert [(cell.path, cell.type_name) for cell in tryte_layout.cells] == [
        ((), ast.TypeName.TRYTE),
    ]
    assert (
        model.return_classification(ast.TypeName.TRYTE)
        is ReturnClass.SCALAR_RETURN_COMPATIBLE
    )

    string_layout = model.fixed_value_layout(ast.TypeName.STRING)
    assert string_layout.kind is ValueLayoutKind.FIXED_STATIC_TEXT
    assert [(cell.path, cell.type_name) for cell in string_layout.cells] == [
        ((), ast.TypeName.STRING),
    ]
    assert (
        model.return_classification(ast.TypeName.STRING)
        is ReturnClass.SCALAR_RETURN_COMPATIBLE
    )


def test_record_value_layout_is_source_of_truth_for_record_wrappers() -> None:
    program, model = _analyze(
        "record Inner:\n"
        "    label: string\n"
        "    code: tryte\n"
        "record Outer:\n"
        "    flag: trit\n"
        "    inner: Inner\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    outer_type = ast.NominalType("Outer", program.location)
    layout = model.fixed_value_layout(outer_type)

    assert layout.kind is ValueLayoutKind.RECORD
    assert [(cell.path, cell.type_name) for cell in layout.cells] == [
        (("flag",), ast.TypeName.TRIT),
        (("inner", "label"), ast.TypeName.STRING),
        (("inner", "code"), ast.TypeName.TRYTE),
    ]
    assert [
        (leaf.path, leaf.type_name) for leaf in model.record_leaves("Outer")
    ] == [(cell.path, cell.type_name) for cell in layout.cells]
    assert model.record_leaf_count("Outer") == layout.cell_count
    assert (
        model.return_classification(outer_type)
        is ReturnClass.AGGREGATE_FIXED_LAYOUT
    )


def test_enum_value_layout_is_tag_first_and_drives_enum_wrappers() -> None:
    program, model = _analyze(
        "record Payload:\n"
        "    text: string\n"
        "    code: tryte\n"
        "enum Result:\n"
        "    Ok(text: string)\n"
        "    Error(payload: Payload)\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    result_type = ast.NominalType("Result", program.location)
    layout = model.fixed_value_layout(result_type)
    enum_layout = model.enum_layout("Result")

    assert layout.kind is ValueLayoutKind.ENUM
    assert [(cell.path, cell.type_name) for cell in layout.cells] == [
        (("tag",), ast.TypeName.TRYTE),
        (("payload", "cell0"), ast.TypeName.STRING),
        (("payload", "cell1"), ast.TypeName.TRYTE),
    ]
    assert [cell.type_name for cell in layout.cells] == list(enum_layout.slot_types)
    assert model.enum_cell_count("Result") == layout.cell_count
    assert (
        model.return_classification(result_type)
        is ReturnClass.AGGREGATE_FIXED_LAYOUT
    )


def test_single_cell_nominal_layouts_remain_scalar_return_compatible() -> None:
    program, model = _analyze(
        "record Box:\n"
        "    value: tryte\n"
        "enum Sign:\n"
        "    Negative\n"
        "    Zero\n"
        "    Positive\n"
        "fn box() -> Box:\n"
        "    return Box(value=1)\n"
        "fn sign() -> Sign:\n"
        "    return Sign.Zero\n"
        "fn main() -> tryte:\n"
        "    return box().value\n"
    )

    assert (
        model.return_classification(ast.NominalType("Box", program.location))
        is ReturnClass.SCALAR_RETURN_COMPATIBLE
    )
    assert (
        model.return_classification(ast.NominalType("Sign", program.location))
        is ReturnClass.SCALAR_RETURN_COMPATIBLE
    )
