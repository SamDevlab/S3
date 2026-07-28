from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def _execute(source: str) -> int:
    return run_source(source, mode=SyntaxMode.V0_6)


def test_execution_len_of_static_text_binding() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    message: string = "hello"\n'
        "    return len(message)\n"
    ) == 5


def test_execution_static_text_binding_concat_and_len() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    left: string = "hel"\n'
        '    right: string = "lo"\n'
        "    message: string = left + right\n"
        "    return len(message)\n"
    ) == 5


def test_execution_static_text_binding_equality() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        '    left: string = "hel"\n'
        '    right: string = "lo"\n'
        "    message: string = left + right\n"
        '    return message == "hello"\n'
    ) == -1


def test_execution_static_text_binding_inequality() -> None:
    assert _execute(
        "fn main() -> trit:\n"
        '    expected: string = "hello"\n'
        '    actual: string = "world"\n'
        "    return actual != expected\n"
    ) == -1


def test_execution_static_text_binding_chain() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        '    a: string = "a"\n'
        '    b: string = a + "b"\n'
        '    c: string = b + "c"\n'
        "    return len(c)\n"
    ) == 3


def test_execution_static_text_binding_escapes_and_unicode() -> None:
    assert _execute(
        "fn main() -> tryte:\n"
        r'    newline: string = "\n"'
        "\n"
        '    unicode: string = "é"\n'
        "    return len(newline) + len(unicode)\n"
    ) == 2
