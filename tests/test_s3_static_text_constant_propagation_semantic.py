from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import SemanticModel, analyze


def _parse(source: str) -> ast.Program:
    return parse(source, mode=SyntaxMode.V0_6)


def _analyze(source: str) -> SemanticModel:
    return analyze(_parse(source))


def test_immutable_static_text_binding_can_feed_len() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        '    message: string = "hello"\n'
        "    return len(message)\n"
    )
    assert model is not None


def test_static_text_bindings_can_be_concatenated() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        '    left: string = "hel"\n'
        '    right: string = "lo"\n'
        "    message: string = left + right\n"
        "    return len(message)\n"
    )
    assert model is not None


def test_static_text_binding_chain_and_equality() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        '    a: string = "a"\n'
        '    b: string = a + "b"\n'
        '    c: string = b + "c"\n'
        '    expected: string = "abc"\n'
        "    same: trit = c == expected\n"
        "    return len(c)\n"
    )
    assert model is not None


def test_static_text_binding_supports_empty_escapes_and_unicode() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        '    empty: string = ""\n'
        r'    newline: string = "\n"'
        "\n"
        '    unicode: string = "é"\n'
        r'    same_newline: trit = newline == "\n"'
        "\n"
        "    return len(empty) + len(newline) + len(unicode)\n"
    )
    assert model is not None


def test_static_text_binding_initializer_registers_final_value() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    left: string = "hel"\n'
        '    right: string = "lo"\n'
        "    message: string = left + right\n"
        "    return len(message)\n"
    )
    model = analyze(program)
    declaration = program.functions[0].body.statements[2]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert model.static_text_of(declaration.initializer) == "hello"


def test_static_text_binding_shadowing_uses_inner_scope() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        '    value: string = "outer"\n'
        "    match 0:\n"
        "        -1:\n"
        "            return 0\n"
        "        0:\n"
        '            value: string = "inner"\n'
        '            same: trit = value == "inner"\n'
        "            match same:\n"
        "                -1:\n"
        "                    return 1\n"
        "                0:\n"
        "                    return 0\n"
        "                1:\n"
        "                    return -1\n"
        "        1:\n"
        "            return len(value)\n"
    )
    assert model is not None


def test_mutable_static_text_binding_is_not_propagated() -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze(
            "fn main() -> tryte:\n"
            '    mut message: string = "hello"\n'
            "    return len(message)\n"
        )

    assert (
        captured.value.diagnostic_code
        is DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
    )


def test_parameter_static_text_is_not_propagated() -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze(
            "fn size(message: string) -> tryte:\n"
            "    return len(message)\n"
            "fn main() -> tryte:\n"
            '    return size("hello")\n'
        )

    assert (
        captured.value.diagnostic_code
        is DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
    )


def test_string_call_result_is_not_propagated() -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze(
            "fn identity(message: string) -> string:\n"
            "    return message\n"
            "fn main() -> tryte:\n"
            '    message: string = identity("hello")\n'
            "    return len(message)\n"
        )

    assert (
        captured.value.diagnostic_code
        is DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
    )


@pytest.mark.parametrize(
    "source,message",
    [
        (
            "fn main() -> tryte:\n"
            "    message: string = future + \"x\"\n"
            '    future: string = "future"\n'
            "    return len(message)\n",
            "undeclared variable 'future'",
        ),
        (
            "fn main() -> tryte:\n"
            "    message: string = message + \"x\"\n"
            "    return len(message)\n",
            "undeclared variable 'message'",
        ),
        (
            "fn main() -> tryte:\n"
            "    a: string = b + \"a\"\n"
            "    b: string = a + \"b\"\n"
            "    return len(a)\n",
            "undeclared variable 'b'",
        ),
        (
            "fn main() -> tryte:\n"
            "    return len(missing)\n",
            "undeclared variable 'missing'",
        ),
    ],
)
def test_static_text_propagation_rejects_unavailable_bindings(
    source: str,
    message: str,
) -> None:
    with pytest.raises(SemanticError, match=message):
        _analyze(source)


def test_static_text_propagation_rejects_mixed_types() -> None:
    with pytest.raises(SemanticError, match="operands of '\\+'"):
        _analyze(
            "fn main() -> tryte:\n"
            '    message: string = "hello"\n'
            "    bad: string = message + 1\n"
            "    return 0\n"
        )


def test_numeric_bindings_are_not_static_text() -> None:
    with pytest.raises(SemanticError, match="len\\(\\) argument must be"):
        _analyze(
            "fn main() -> tryte:\n"
            "    size: tryte = 5\n"
            "    return len(size)\n"
        )
