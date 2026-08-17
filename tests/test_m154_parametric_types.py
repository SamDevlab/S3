from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.pipeline import compile_source, run_source


def test_parametric_record_is_monomorphized_before_semantic_analysis() -> None:
    source = (
        "record Box<T: value>:\n"
        "    value: T\n"
        "fn read(box: Box<i64>) -> i64:\n"
        "    return box.value\n"
        "fn main() -> i64:\n"
        "    box: Box<i64> = Box<i64>(value=7)\n"
        "    return read(box)\n"
    )

    compilation = compile_source(source, optimization="O0")
    assert [record.name for record in compilation.ast.records] == [
        "__s3_generic_type__Box__i64",
    ]
    assert run_source(source, optimization="O0") == 7
    assert run_source(source, optimization="O1") == 7


def test_parametric_enum_constructor_and_payload_match_are_monomorphized() -> None:
    source = (
        "enum Maybe<T: value>:\n"
        "    Some(value: T)\n"
        "    None\n"
        "fn inspect(value: Maybe<i64>) -> i64:\n"
        "    match value:\n"
        "        Maybe<i64>.Some(value):\n"
        "            return value\n"
        "        Maybe<i64>.None:\n"
        "            return 0\n"
        "fn main() -> i64:\n"
        "    value: Maybe<i64> = Maybe<i64>.Some(value=9)\n"
        "    return inspect(value)\n"
    )

    compilation = compile_source(source, optimization="O0")
    assert [enum.name for enum in compilation.ast.enums] == [
        "__s3_generic_type__Maybe__i64",
    ]
    assert run_source(source, optimization="O0") == 9
    assert run_source(source, optimization="O1") == 9


def test_parametric_type_requires_explicit_arguments() -> None:
    source = (
        "record Box<T: value>:\n"
        "    value: T\n"
        "fn main() -> i64:\n"
        "    box: Box = Box(value=7)\n"
        "    return box.value\n"
    )

    with pytest.raises(SemanticError):
        compile_source(source)


def test_parametric_type_constraint_rejects_nominal_arguments() -> None:
    source = (
        "record Inner:\n"
        "    value: i64\n"
        "record Box<T: value>:\n"
        "    value: T\n"
        "fn main() -> i64:\n"
        "    box: Box<Inner> = Box<Inner>(value=Inner(value=7))\n"
        "    return box.value.value\n"
    )

    with pytest.raises(SemanticError) as error:
        compile_source(source)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE
