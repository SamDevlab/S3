from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_execution_static_text_equal_true() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        '    return "abc" == "abc"\n'
    ) == -1


def test_execution_static_text_equal_false() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        '    return "abc" == "xyz"\n'
    ) == 0


def test_execution_static_text_not_equal_true() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        '    return ("a" + "b") != "ac"\n'
    ) == -1


def test_execution_static_text_not_equal_false() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        '    return ("a" + "b") != "ab"\n'
    ) == 0


def test_execution_static_text_equality_in_numeric_context() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    same: trit = "abc" == "abc"\n'
        "    match same:\n"
        "        -1:\n"
        "            return 7\n"
        "        0:\n"
        "            return 0\n"
        "        1:\n"
        "            return -1\n"
    ) == 7


def test_execution_static_text_equality_with_len_result() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        '    return len("abc") == 3\n'
    ) == -1
