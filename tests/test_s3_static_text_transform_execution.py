from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_execution_static_text_upper_len() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    return len(upper("hello"))\n'
    ) == 5


def test_execution_static_text_lower_equality() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        '    return lower("WORLD") == "world"\n'
    ) == -1


def test_execution_static_text_trim_find() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    return find(trim("  abc  "), "b")\n'
    ) == 1


def test_execution_static_text_repeat_len() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    return len(repeat("xyz", 4))\n'
    ) == 12


def test_execution_static_text_replace_contains() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        '    return contains(replace("hello world", "world", "S3"), "S3")\n'
    ) == -1
