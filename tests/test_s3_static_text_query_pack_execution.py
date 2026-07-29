from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_execution_static_text_find() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    return find("hello", "ll")\n'
    ) == 2


def test_execution_static_text_contains_slice() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        '    return contains("hello"[1:4], "ll")\n'
    ) == -1


def test_execution_static_text_slice_materialized_length() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    part: string = "hello"[1:4]\n'
        "    return len(part)\n"
    ) == 3


def test_execution_static_text_prefix_suffix_and_missing_find() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    prefix: trit = starts_with("hello", "he")\n'
        '    suffix: trit = ends_with("hello", "lo")\n'
        '    missing: tryte = find("hello", "xyz")\n'
        "    return missing\n"
    ) == -1
