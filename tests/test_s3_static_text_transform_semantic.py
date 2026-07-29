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


def _initializer(program: ast.Program, index: int) -> ast.Expression:
    declaration = program.functions[0].body.statements[index]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert not isinstance(declaration.initializer, ast.ArrayLiteral)
    return declaration.initializer


def test_static_text_transform_builtins_evaluations() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    u: string = upper("hello")\n'
        '    l: string = lower("WORLD")\n'
        '    t: string = trim("  hello  ")\n'
        '    rep: string = repeat("ab", 3)\n'
        '    repl: string = replace("foo bar", "bar", "baz")\n'
        "    return len(u) + len(l) + len(t) + len(rep) + len(repl)\n"
    )
    model = analyze(program)

    assert model.static_text_of(_initializer(program, 0)) == "HELLO"
    assert model.static_text_of(_initializer(program, 1)) == "world"
    assert model.static_text_of(_initializer(program, 2)) == "hello"
    assert model.static_text_of(_initializer(program, 3)) == "ababab"
    assert model.static_text_of(_initializer(program, 4)) == "foo baz"


def test_static_text_transform_nested_and_combined() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    nested: string = upper(trim("  abc  "))\n'
        '    chain: string = replace(repeat("a", 2), "a", "x")\n'
        '    sliced: string = lower("HELLO")[0:2]\n'
        "    return len(nested) + len(chain) + len(sliced)\n"
    )
    model = analyze(program)

    assert model.static_text_of(_initializer(program, 0)) == "ABC"
    assert model.static_text_of(_initializer(program, 1)) == "xx"
    assert model.static_text_of(_initializer(program, 2)) == "he"


def test_static_text_transform_empty_strings() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    u: string = upper("")\n'
        '    l: string = lower("")\n'
        '    t: string = trim("")\n'
        "    return len(u) + len(l) + len(t)\n"
    )
    model = analyze(program)

    assert model.static_text_of(_initializer(program, 0)) == ""
    assert model.static_text_of(_initializer(program, 1)) == ""
    assert model.static_text_of(_initializer(program, 2)) == ""


def test_static_text_trim_whitespace_contract() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    t: string = trim("  \\n  abc  \\n  ")\n'
        "    return len(t)\n"
    )
    model = analyze(program)
    assert model.static_text_of(_initializer(program, 0)) == "abc"


def test_static_text_repeat_audited_cases() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    r1: string = repeat("", 0)\n'
        '    r2: string = repeat("", 5)\n'
        '    r3: string = repeat("abc", 0)\n'
        '    r4: string = repeat("abc", 1)\n'
        '    r5: string = repeat("abc", 2)\n'
        "    return len(r1) + len(r2) + len(r3) + len(r4) + len(r5)\n"
    )
    model = analyze(program)

    assert model.static_text_of(_initializer(program, 0)) == ""
    assert model.static_text_of(_initializer(program, 1)) == ""
    assert model.static_text_of(_initializer(program, 2)) == ""
    assert model.static_text_of(_initializer(program, 3)) == "abc"
    assert model.static_text_of(_initializer(program, 4)) == "abcabc"


def test_static_text_replace_audited_cases() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        '    r1: string = replace("", "", "")\n'
        '    r2: string = replace("", "a", "")\n'
        '    r3: string = replace("abc", "", "X")\n'
        '    r4: string = replace("aaa", "aa", "b")\n'
        '    r5: string = replace("abc", "x", "y")\n'
        "    return len(r1) + len(r2) + len(r3) + len(r4) + len(r5)\n"
    )
    model = analyze(program)

    assert model.static_text_of(_initializer(program, 0)) == ""
    assert model.static_text_of(_initializer(program, 1)) == ""
    assert model.static_text_of(_initializer(program, 2)) == "XaXbXcX"
    assert model.static_text_of(_initializer(program, 3)) == "ba"
    assert model.static_text_of(_initializer(program, 4)) == "abc"


def test_static_text_transform_negative_repeat_count_raises() -> None:
    with pytest.raises(SemanticError) as exc_info:
        _analyze(
            "fn main() -> tryte:\n"
            '    s: string = repeat("abc", -1)\n'
            "    return len(s)\n"
        )
    assert "repeat count must be non-negative" in str(exc_info.value)


def test_static_text_transform_invalid_arg_count_raises() -> None:
    with pytest.raises(SemanticError) as exc_info:
        _analyze(
            "fn main() -> tryte:\n"
            '    s: string = upper("a", "b")\n'
            "    return len(s)\n"
        )
    assert exc_info.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE
    assert "builtin 'upper' expects 1 argument(s)" in str(exc_info.value)


@pytest.mark.parametrize(
    "code",
    [
        'fn main() -> tryte:\n    x: tryte = 5\n    s: string = upper(x)\n    return len(s)\n',
        'fn main() -> tryte:\n    x: tryte = 5\n    s: string = lower(x)\n    return len(s)\n',
        'fn main() -> tryte:\n    x: tryte = 5\n    s: string = trim(x)\n    return len(s)\n',
        'fn main() -> tryte:\n    x: tryte = 5\n    s: string = repeat(x, 2)\n    return len(s)\n',
        'fn main() -> tryte:\n    x: tryte = 5\n    s: string = replace(x, "a", "b")\n    return len(s)\n',
    ],
)
def test_static_text_transform_non_constant_args_raise_semantic_error(code: str) -> None:
    with pytest.raises(SemanticError) as exc_info:
        _analyze(code)
    assert "requires compile-time static text" in str(exc_info.value)


def test_static_text_transform_fallback_to_user_defined_function() -> None:
    program = _parse(
        "fn upper(s: string) -> string:\n"
        "    return s\n"
        "fn main() -> tryte:\n"
        '    s: string = upper("hello")\n'
        "    return len(s)\n"
    )
    model = analyze(program)
    main_func = next(f for f in program.functions if f.name == "main")
    decl = main_func.body.statements[0]
    assert isinstance(decl, ast.VariableDeclaration)
    assert model.static_text_of(decl.initializer) == "HELLO"

