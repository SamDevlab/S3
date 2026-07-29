from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import SemanticModel, analyze


def _parse(source: str) -> ast.Program:
    return parse(source, mode=SyntaxMode.V0_6)


def _analyze(source: str) -> SemanticModel:
    return analyze(_parse(source))


def _initializer(program: ast.Program, index: int) -> ast.Expression:
    declaration = program.functions[0].body.statements[index]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert not isinstance(declaration.initializer, ast.ArrayLiteral)
    return declaration.initializer


def test_static_text_slicing_records_final_text_values() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    full: string = "hello"[0:5]\n'
        '    prefix: string = "hello"[0:2]\n'
        '    suffix: string = "hello"[3:5]\n'
        '    empty: string = "hello"[2:2]\n'
        "    return len(full) + len(prefix) + len(suffix) + len(empty)\n"
    )
    model = analyze(program)

    assert model.static_text_of(_initializer(program, 0)) == "hello"
    assert model.static_text_of(_initializer(program, 1)) == "he"
    assert model.static_text_of(_initializer(program, 2)) == "lo"
    assert model.static_text_of(_initializer(program, 3)) == ""


def test_static_text_slicing_accepts_concat_bindings_index_results_and_unicode() -> None:
    accented = chr(225)
    program = _parse(
        "fn main() -> tryte:\n"
        '    left: string = "he"\n'
        '    right: string = "llo"\n'
        "    text: string = left + right\n"
        "    part: string = text[1:4]\n"
        '    letter: string = "abc"[1]\n'
        "    again: string = letter[0:1]\n"
        f'    accent: string = "{accented}b"[0:1]\n'
        "    return len(part) + len(again) + len(accent)\n"
    )
    model = analyze(program)

    assert model.static_text_of(_initializer(program, 3)) == "ell"
    assert model.static_text_of(_initializer(program, 5)) == "b"
    assert model.static_text_of(_initializer(program, 6)) == accented


def test_static_text_slicing_feeds_len_equality_concat_and_queries() -> None:
    _analyze(
        "fn main() -> tryte:\n"
        '    part: string = "hello"[1:4]\n'
        "    size: tryte = len(part)\n"
        '    same: trit = part == "ell"\n'
        '    combined: string = "x" + part\n'
        '    has: trit = contains(part, "ll")\n'
        "    return size + len(combined)\n"
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("contains", -1),
        ("starts_with", -1),
        ("ends_with", -1),
        ("find", 2),
    ],
)
def test_static_text_query_builtins_record_constant_results(
    name: str,
    expected: int,
) -> None:
    fragment = "ll" if name in ("contains", "find") else ("he" if name == "starts_with" else "lo")
    program = _parse(
        "fn main() -> tryte:\n"
        f'    result: {"tryte" if name == "find" else "trit"} = {name}("hello", "{fragment}")\n'
        "    return 0\n"
    )
    model = analyze(program)

    assert model.constant_value_of(_initializer(program, 0)) == expected


def test_static_text_query_builtins_handle_empty_and_missing_fragments() -> None:
    _analyze(
        "fn main() -> tryte:\n"
        '    c1: trit = contains("hello", "")\n'
        '    c2: trit = contains("", "")\n'
        '    c3: trit = contains("", "a")\n'
        '    p: trit = starts_with("hello", "")\n'
        '    s: trit = ends_with("hello", "")\n'
        '    f1: tryte = find("hello", "")\n'
        '    f2: tryte = find("hello", "xyz")\n'
        '    f3: tryte = find("", "")\n'
        "    return f1 + f2 + f3\n"
    )


def test_static_text_query_builtins_accept_bindings_concat_slices_and_index_results() -> None:
    _analyze(
        "fn main() -> tryte:\n"
        '    left: string = "he"\n'
        '    right: string = "llo"\n'
        "    text: string = left + right\n"
        "    part: string = text[1:4]\n"
        '    letter: string = "abc"[1]\n'
        '    has: trit = contains(left + right, part)\n'
        "    pos: tryte = find(\"abc\", letter)\n"
        "    return pos\n"
    )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('    part: string = "hello"[-1:2]\n', "static text slice bounds must be non-negative"),
        ('    part: string = "hello"[3:2]\n', "static text slice start 3 exceeds end 2"),
        ('    part: string = "hello"[0:6]\n', "static text slice end 6 is outside text bounds [0, 5]"),
        ('    part: string = ""[0:1]\n', "static text slice end 1 is outside text bounds [0, 0]"),
        (
            "    start: tryte = 1\n"
            '    part: string = "hello"[start:4]\n',
            "static text slice bounds must be non-negative integer literals known at compile time",
        ),
        (
            '    mut text: string = "hello"\n'
            "    part: string = text[1:4]\n",
            "static text slicing requires a compile-time static text expression",
        ),
        (
            "    values: tryte[3] = [1, 2, 3]\n"
            "    part: string = values[1:2]\n",
            "array slicing is not supported",
        ),
        ("    part: string = 1[0:1]\n", "static text slicing requires a compile-time static text expression"),
        ('    part: tryte = "hello"[1:4]\n', "slice expression has type string; expected tryte"),
    ],
)
def test_static_text_slicing_rejects_invalid_operands(
    source: str,
    message: str,
) -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze("fn main() -> tryte:\n" + source + "    return 0\n")
    assert message in str(captured.value)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('    result: trit = contains("hello")\n', "expects 2 argument"),
        ('    result: trit = contains("hello", "ell", "x")\n', "expects 2 argument"),
        (
            '    mut text: string = "hello"\n'
            '    result: trit = contains(text, "e")\n',
            "requires compile-time static text arguments",
        ),
        (
            "fn check(text: string) -> trit:\n"
            '    return contains(text, "e")\n'
            "fn main() -> tryte:\n"
            "    return 0\n",
            "requires compile-time static text arguments",
        ),
        ('    result: trit = contains(1, "e")\n', "requires compile-time static text arguments"),
        ('    result: tryte = contains("hello", "e")\n', "call to 'contains' has type trit; expected tryte"),
        ('    result: trit = find("hello", "e")\n', "call to 'find' has type tryte; expected trit"),
    ],
)
def test_static_text_query_builtins_reject_invalid_calls(
    source: str,
    message: str,
) -> None:
    full_source = (
        source
        if source.startswith("fn ")
        else "fn main() -> tryte:\n" + source + "    return 0\n"
    )
    with pytest.raises(SemanticError) as captured:
        _analyze(full_source)
    assert message in str(captured.value)
