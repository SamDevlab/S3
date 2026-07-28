from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_execution_static_text_len_literal() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    return len("abc")\n'
    ) == 3


def test_execution_static_text_len_concatenation() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    return len("hello" + " world")\n'
    ) == 11


def test_execution_static_text_len_nested_expression() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    return len(("a" + "b") + "c") + len("")\n'
    ) == 3


def test_execution_static_text_len_escapes_and_unicode() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        r'    return len("\n") + len("\"") + len("\\") + len("é")'
        "\n"
    ) == 4


def test_execution_array_len_still_works() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        "    values: tryte[5] = [1, 2, 3, 4, 5]\n"
        '    return len(values) + len("ab")\n'
    ) == 7
