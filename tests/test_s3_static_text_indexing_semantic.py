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


def _decl_initializer(program: ast.Program, index: int) -> ast.Expression:
    declaration = program.functions[0].body.statements[index]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert not isinstance(declaration.initializer, ast.ArrayLiteral)
    return declaration.initializer


def test_static_text_indexing_resolves_first_middle_and_last_characters() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    first: string = "abc"[0]\n'
        '    middle: string = "abc"[1]\n'
        '    last: string = "abc"[2]\n'
        "    return len(first) + len(middle) + len(last)\n"
    )
    model = analyze(program)

    assert model.static_text_of(_decl_initializer(program, 0)) == "a"
    assert model.static_text_of(_decl_initializer(program, 1)) == "b"
    assert model.static_text_of(_decl_initializer(program, 2)) == "c"


def test_static_text_indexing_accepts_concat_and_immutable_binding_chain() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    left: string = "he"\n'
        '    right: string = "llo"\n'
        "    message: string = left + right\n"
        "    letter: string = message[4]\n"
        '    same: trit = letter == "o"\n'
        "    return len(letter)\n"
    )
    model = analyze(program)

    assert model.static_text_of(_decl_initializer(program, 3)) == "o"


def test_static_text_indexing_result_feeds_len_equality_and_concatenation() -> None:
    _analyze(
        "fn main() -> tryte:\n"
        '    letter: string = "abc"[1]\n'
        "    size: tryte = len(letter)\n"
        '    same: trit = letter == "b"\n'
        '    value: string = "x" + letter\n'
        "    return size + len(value)\n"
    )


def test_static_text_indexing_handles_empty_escape_newline_and_unicode_code_points() -> None:
    accented = chr(225)
    emoji = chr(0x1F600)
    program = _parse(
        "fn main() -> tryte:\n"
        r'    newline: string = "\n"[0]'
        "\n"
        r'    quote: string = "\""[0]'
        "\n"
        f'    accent: string = "{accented}"[0]\n'
        f'    face: string = "{emoji}"[0]\n'
        "    return len(newline) + len(quote) + len(accent) + len(face)\n"
    )
    model = analyze(program)

    assert model.static_text_of(_decl_initializer(program, 0)) == "\n"
    assert model.static_text_of(_decl_initializer(program, 1)) == '"'
    assert model.static_text_of(_decl_initializer(program, 2)) == accented
    assert model.static_text_of(_decl_initializer(program, 3)) == emoji


def test_static_text_indexing_uses_shadowed_static_binding() -> None:
    _analyze(
        "fn main() -> tryte:\n"
        '    value: string = "outer"\n'
        "    match 0:\n"
        "        -1:\n"
        "            return 0\n"
        "        0:\n"
        '            value: string = "inner"\n'
        "            letter: string = value[0]\n"
        "            return len(letter)\n"
        "        1:\n"
        "            return len(value)\n"
    )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            '    letter: string = ""[0]\n',
            "static text index 0 is outside text bounds [0, 0)",
        ),
        (
            '    letter: string = "a"[1]\n',
            "static text index 1 is outside text bounds [0, 1)",
        ),
        (
            '    letter: string = "abc"[3]\n',
            "static text index 3 is outside text bounds [0, 3)",
        ),
        (
            '    letter: string = "abc"[-1]\n',
            "static text index must be non-negative",
        ),
    ],
)
def test_static_text_indexing_rejects_invalid_literal_bounds(
    source: str,
    message: str,
) -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze("fn main() -> tryte:\n" + source + "    return 0\n")
    assert message in str(captured.value)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            "    index: string = \"1\"\n"
            '    letter: string = "abc"[index]\n',
            "variable 'index' has type string; expected tryte",
        ),
        (
            '    mut text: string = "abc"\n'
            "    letter: string = text[0]\n",
            "string indexing requires a compile-time static text expression",
        ),
        (
            "    letter: string = 1[0]\n",
            "indexed target has type tryte; expected array or compile-time static text",
        ),
        (
            '    letter: tryte = "abc"[1]\n',
            "index expression has type string; expected tryte",
        ),
    ],
)
def test_static_text_indexing_rejects_unsupported_operands(
    source: str,
    message: str,
) -> None:
    with pytest.raises(SemanticError, match=message):
        _analyze("fn main() -> tryte:\n" + source + "    return 0\n")


def test_static_text_indexing_rejects_parameter_and_call_result_text() -> None:
    with pytest.raises(
        SemanticError,
        match="string indexing requires a compile-time static text expression",
    ):
        _analyze(
            "fn first(text: string) -> string:\n"
            "    return text[0]\n"
            "fn main() -> tryte:\n"
            '    return len(first("abc"))\n'
        )

    with pytest.raises(
        SemanticError,
        match="string indexing requires a compile-time static text expression",
    ):
        _analyze(
            "fn identity(text: string) -> string:\n"
            "    return text\n"
            "fn main() -> tryte:\n"
            '    letter: string = identity("abc")[0]\n'
            "    return len(letter)\n"
        )


def test_string_index_assignment_is_still_rejected() -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze(
            "fn main() -> tryte:\n"
            '    mut text: string = "abc"\n'
            '    text[0] = "x"\n'
            "    return 0\n"
        )

    assert (
        captured.value.diagnostic_code
        is DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
    )
