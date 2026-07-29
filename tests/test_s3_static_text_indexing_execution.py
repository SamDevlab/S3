from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_execution_static_text_indexing_letter_length() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    value: string = "hello"\n'
        "    letter: string = value[1]\n"
        "    return len(letter)\n"
    ) == 1


def test_execution_static_text_indexing_equality_result() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        '    value: string = "hello"\n'
        '    return value[1] == "e"\n'
    ) == -1


def test_execution_static_text_indexing_concat_then_len() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    value: string = "hello"\n'
        '    combined: string = "x" + value[1]\n'
        "    return len(combined)\n"
    ) == 2
