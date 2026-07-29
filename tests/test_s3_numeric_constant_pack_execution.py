from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_execution_find_result_propagates_as_tryte() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    position: tryte = find("hello", "ll")\n'
        "    return position\n"
    ) == 2


def test_execution_len_result_feeds_arithmetic() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    size: tryte = len("hello")\n'
        "    return size - 1\n"
    ) == 4


def test_execution_constant_slice_bounds_from_find_and_arithmetic() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    start: tryte = find("hello", "e")\n'
        "    end: tryte = start + 3\n"
        '    part: string = "hello"[start:end]\n'
        "    return len(part)\n"
    ) == 3


def test_execution_constant_index_from_find() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        '    position: tryte = find("hello", "ll")\n'
        '    letter: string = "hello"[position]\n'
        '    return letter == "l"\n'
    ) == -1
