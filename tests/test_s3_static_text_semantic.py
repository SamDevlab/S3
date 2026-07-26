from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze


def _analyze(source: str):
    program = parse(source, mode=SyntaxMode.V0_6)
    return program, analyze(program)


def test_static_string_bindings_parameters_and_helper_return_are_typed() -> None:
    program, model = _analyze(
        "fn pick(left: string, right: string) -> string:\n"
        "    return right\n"
        "fn main() -> tryte:\n"
        '    first: string = "alpha"\n'
        '    second: string = pick(first, "beta")\n'
        "    return 0\n"
    )

    assert model.functions["pick"].parameter_types == (
        ast.TypeName.STRING,
        ast.TypeName.STRING,
    )
    assert model.functions["pick"].return_type is ast.TypeName.STRING

    first = program.functions[1].body.statements[0]
    second = program.functions[1].body.statements[1]
    assert isinstance(first, ast.VariableDeclaration)
    assert isinstance(second, ast.VariableDeclaration)
    assert model.type_of(first.initializer) is ast.TypeName.STRING
    assert model.type_of(second.initializer) is ast.TypeName.STRING


def test_mutable_static_string_binding_can_be_reassigned() -> None:
    _analyze(
        "fn main() -> tryte:\n"
        '    mut current: string = "first"\n'
        '    current = "second"\n'
        "    return 0\n"
    )


def test_entry_function_cannot_return_string() -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze('fn main() -> string:\n    return "hello"\n')

    assert captured.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_RETURN_TYPE
    assert captured.value.message == "entry function 'main' cannot return string"


def test_string_literal_in_tryte_return_is_type_mismatch() -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze('fn main() -> tryte:\n    return "hello"\n')

    assert captured.value.diagnostic_code is DiagnosticCode.SEMANTIC_TYPE_MISMATCH
    assert captured.value.message == "string literal has type string; expected tryte"


def test_integer_initializer_for_string_binding_is_type_mismatch() -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze("fn main() -> tryte:\n    value: string = 1\n    return 0\n")

    assert captured.value.diagnostic_code is DiagnosticCode.SEMANTIC_TYPE_MISMATCH
    assert (
        captured.value.message
        == "initializer for 'value' has type tryte; expected string"
    )


def test_wrong_string_argument_type_uses_argument_diagnostic() -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze(
            "fn accepts(value: string) -> tryte:\n"
            "    return 0\n"
            "fn main() -> tryte:\n"
            "    return accepts(1)\n"
        )

    assert (
        captured.value.diagnostic_code
        is DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE
    )
    assert (
        captured.value.message
        == "argument 1 to 'accepts' has type tryte; expected string"
    )


@pytest.mark.parametrize(
    "source,message",
    [
        (
            "fn main() -> tryte:\n"
            '    left: string = "a"\n'
            '    right: string = "b"\n'
            "    combined: string = left + right\n"
            "    return 0\n",
            "operator '+' is not supported for string values",
        ),
        (
            "fn main() -> tryte:\n"
            '    left: string = "a"\n'
            '    right: string = "b"\n'
            "    same: trit = left == right\n"
            "    return 0\n",
            "operator '==' is not supported for string values",
        ),
        (
            "fn main() -> tryte:\n"
            '    value: string = "abc"\n'
            "    size: tryte = len(value)\n"
            "    return size\n",
            "len() is not supported for string values",
        ),
        (
            "fn main() -> tryte:\n"
            '    value: string = "abc"\n'
            "    first: tryte = value[0]\n"
            "    return first\n",
            "string indexing is not supported",
        ),
        (
            "fn main() -> tryte:\n"
            '    mut value: string = "a"\n'
            '    value += "b"\n'
            "    return 0\n",
            "compound assignment is not supported for string values",
        ),
    ],
)
def test_static_string_operations_outside_0_53_are_rejected(
    source: str,
    message: str,
) -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze(source)

    assert (
        captured.value.diagnostic_code
        is DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
    )
    assert captured.value.message == message


def test_string_arrays_are_outside_0_53() -> None:
    with pytest.raises(SemanticError, match="arrays of string are not supported"):
        _analyze(
            "fn main() -> tryte:\n"
            '    values: string[2] = ["a", "b"]\n'
            "    return 0\n"
        )


def test_unsupported_static_string_escape_is_semantic_error() -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze("fn main() -> tryte:\n" r'    value: string = "bad\t"' "\n    return 0\n")

    assert captured.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_PROGRAM
    assert "unsupported static text escape" in captured.value.message
