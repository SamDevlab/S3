from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_execution_tryte_constant_comparisons() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        "    return 10 > 5\n"
    ) == -1

    assert _execute(
        "fn main() -> trit:\n"
        "    return 5 >= 10\n"
    ) == 0


def test_execution_trit_constant_comparisons() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        "    return -1 < 0\n"
    ) == -1


def test_execution_string_constant_comparisons() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        '    return "abc" < "def"\n'
    ) == -1

    assert _execute(
        "fn main() -> trit:\n"
        '    return "abc" >= "def"\n'
    ) == 0

    assert _execute(
        "fn main() -> trit:\n"
        '    return "hello" == "hello"\n'
    ) == -1
