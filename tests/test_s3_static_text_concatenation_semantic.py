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


def _semantic_error(source: str) -> SemanticError:
    with pytest.raises(SemanticError) as captured:
        _analyze(source)
    return captured.value


@pytest.mark.parametrize(
    "expression",
    [
        '"a" + "b"',
        '"a" + "b" + "c"',
        '("a" + "b") + "c"',
        '"a" + ("b" + "c")',
        '"" + "a"',
        '"a" + ""',
        '"" + ""',
        '"á" + "β"',
        '"😀" + "S3"',
        r'"line\n" + "next"',
        r'"a\"" + "b"',
        r'"a\\" + "b"',
    ],
)
def test_literal_only_static_text_concatenation_is_typed(
    expression: str,
) -> None:
    program, model = _analyze(
        "fn main() -> tryte:\n"
        f"    value: string = {expression}\n"
        "    return 0\n"
    )

    declaration = program.functions[0].body.statements[0]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert model.type_of(declaration.initializer) is ast.TypeName.STRING


def test_constant_static_text_concatenation_can_initialize_mutable_binding() -> None:
    _analyze(
        "fn main() -> tryte:\n"
        '    mut value: string = "a" + "b"\n'
        "    return 0\n"
    )


def test_constant_static_text_concatenation_can_be_argument_and_return() -> None:
    _analyze(
        "fn identity(value: string) -> string:\n"
        "    return value\n"
        "fn make() -> string:\n"
        '    return "TRET " + "r1"\n'
        "fn main() -> tryte:\n"
        '    value: string = identity("a" + "b")\n'
        "    return 0\n"
    )


@pytest.mark.parametrize(
    "source",
    [
        (
            "fn main() -> tryte:\n"
            '    mut prefix: string = "TRET "\n'
            '    message: string = prefix + "r1"\n'
            "    return 0\n"
        ),
        (
            "fn main() -> tryte:\n"
            '    mut name: string = "r1"\n'
            '    message: string = "TRET " + name\n'
            "    return 0\n"
        ),
        (
            "fn join(name: string) -> string:\n"
            '    return "TRET " + name\n'
            "fn main() -> tryte:\n"
            "    return 0\n"
        ),
        (
            "fn make() -> string:\n"
            '    return "r1"\n'
            "fn main() -> tryte:\n"
            '    message: string = "TRET " + make()\n'
            "    return 0\n"
        ),
    ],
)
def test_runtime_dependent_string_concatenation_is_rejected(
    source: str,
) -> None:
    error = _semantic_error(source)

    assert (
        error.diagnostic_code
        is DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
    )
    assert (
        error.message
        == "string concatenation requires a compile-time static text expression"
    )


@pytest.mark.parametrize(
    "expression",
    [
        '"x" + 1',
        '1 + "x"',
    ],
)
def test_mixed_string_numeric_concatenation_is_type_mismatch(
    expression: str,
) -> None:
    error = _semantic_error(
        "fn main() -> tryte:\n"
        f"    value: string = {expression}\n"
        "    return 0\n"
    )

    assert error.diagnostic_code is DiagnosticCode.SEMANTIC_TYPE_MISMATCH
    assert "operands of '+'" in error.message


def test_string_plus_array_value_is_rejected_before_lowering() -> None:
    error = _semantic_error(
        "fn main() -> tryte:\n"
        "    values: tryte[3] = [-1, 0, 1]\n"
        '    value: string = "x" + values\n'
        "    return 0\n"
    )

    assert error.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_PROGRAM
    assert error.message == "array 'values' cannot be used as a scalar value"


def test_string_plus_array_element_is_type_mismatch() -> None:
    error = _semantic_error(
        "fn main() -> tryte:\n"
        "    values: tryte[1] = [0]\n"
        '    value: string = "x" + values[0]\n'
        "    return 0\n"
    )

    assert error.diagnostic_code is DiagnosticCode.SEMANTIC_TYPE_MISMATCH
    assert "operands of '+'" in error.message
