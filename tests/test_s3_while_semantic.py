from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze


def _compile(source: str):
    return analyze(parse(source, mode=SyntaxMode.V0_6))


def test_condition_zero_returns() -> None:
    with pytest.raises(SemanticError, match="has a path without returning"):
        _compile(
            "fn foo() -> tryte:\n"
            "    while 0:\n"
            "        return 1\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )


def test_condition_positive_returns() -> None:
    with pytest.raises(SemanticError, match="has a path without returning"):
        _compile(
            "fn foo() -> tryte:\n"
            "    while 1:\n"
            "        return 1\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )


def test_condition_negative_returns() -> None:
    with pytest.raises(SemanticError, match="has a path without returning"):
        _compile(
            "fn foo() -> tryte:\n"
            "    while -1:\n"
            "        return 1\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )


def test_return_after_while() -> None:
    _compile(
        "fn foo(condition: trit) -> tryte:\n"
        "    while condition:\n"
        "        return 1\n"
        "    return 0\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )


def test_declaration_and_return_after_while() -> None:
    _compile(
        "fn foo(condition: trit) -> tryte:\n"
        "    while condition:\n"
        "        return 1\n"
        "    mut value: tryte = 0\n"
        "    return value\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )


def test_nested_while_no_return_after() -> None:
    with pytest.raises(SemanticError, match="has a path without returning"):
        _compile(
            "fn foo(condition: trit) -> tryte:\n"
            "    while condition:\n"
            "        while condition:\n"
            "            return 1\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )


def test_match_inside_while_no_return_after() -> None:
    with pytest.raises(SemanticError, match="has a path without returning"):
        _compile(
            "fn foo(condition: trit) -> tryte:\n"
            "    while condition:\n"
            "        match condition:\n"
            "            -1:\n"
            "                return 1\n"
            "            0:\n"
            "                return 1\n"
            "            1:\n"
            "                return 1\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )


def test_while_inside_match_branch() -> None:
    with pytest.raises(SemanticError, match="has a path without returning"):
        _compile(
            "fn foo(condition: trit) -> tryte:\n"
            "    match condition:\n"
            "        -1:\n"
            "            while condition:\n"
            "                return 1\n"
            "        0:\n"
            "            return 1\n"
            "        1:\n"
            "            return 1\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )


def test_unreachable_inside_while_body() -> None:
    with pytest.raises(SemanticError, match="unreachable statement"):
        _compile(
            "fn foo(condition: trit) -> tryte:\n"
            "    while condition:\n"
            "        return 1\n"
            "        mut value: tryte = 0\n"
            "    return 0\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )


def test_pipeline_stops_before_lowering(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def fake_lower(*args, **kwargs):
        nonlocal called
        called = True
        return None

    import bootstrap.s3.pipeline as pipeline
    monkeypatch.setattr(pipeline, "lower", fake_lower)

    with pytest.raises(SemanticError):
        _compile(
            "fn foo() -> tryte:\n"
            "    while 0:\n"
            "        return 1\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )

    assert not called


def test_break_outside_loop_rejected() -> None:
    with pytest.raises(SemanticError, match="break outside loop"):
        _compile(
            "fn foo() -> tryte:\n"
            "    break\n"
            "    return 0\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )


def test_continue_outside_loop_rejected() -> None:
    with pytest.raises(SemanticError, match="continue outside loop"):
        _compile(
            "fn foo() -> tryte:\n"
            "    continue\n"
            "    return 0\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )


def test_valid_break_and_continue_inside_while() -> None:
    _compile(
        "fn foo(cond: trit) -> tryte:\n"
        "    while cond:\n"
        "        match cond:\n"
        "            -1:\n"
        "                continue\n"
        "            0:\n"
        "                break\n"
        "            1:\n"
        "                break\n"
        "    return 0\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )


def test_unreachable_after_break() -> None:
    with pytest.raises(SemanticError, match="unreachable statement"):
        _compile(
            "fn foo(cond: trit) -> tryte:\n"
            "    while cond:\n"
            "        break\n"
            "        mut x: tryte = 1\n"
            "    return 0\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )


def test_unreachable_after_continue() -> None:
    with pytest.raises(SemanticError, match="unreachable statement"):
        _compile(
            "fn foo(cond: trit) -> tryte:\n"
            "    while cond:\n"
            "        continue\n"
            "        mut x: tryte = 1\n"
            "    return 0\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )


def test_break_does_not_satisfy_return() -> None:
    with pytest.raises(SemanticError, match="has a path without returning"):
        _compile(
            "fn foo(cond: trit) -> tryte:\n"
            "    while cond:\n"
            "        break\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )


def test_continue_does_not_satisfy_return() -> None:
    with pytest.raises(SemanticError, match="has a path without returning"):
        _compile(
            "fn foo(cond: trit) -> tryte:\n"
            "    while cond:\n"
            "        continue\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )


def test_loop_depth_restored_on_body_error() -> None:
    with pytest.raises(SemanticError, match="undeclared variable"):
        _compile(
            "fn foo(cond: trit) -> tryte:\n"
            "    while cond:\n"
            "        invalid_var = 1\n"
            "    return 0\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )

