from __future__ import annotations

import pytest

from bootstrap.s3.ir import IRFunction
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.passes import _FunctionPass, _PassManager
from bootstrap.s3.pipeline import compile_source


def test_pass_manager_initialization_and_names() -> None:
    pass_a = _FunctionPass("pass-a", lambda fn: fn)
    pass_b = _FunctionPass("pass-b", lambda fn: fn)
    pm = _PassManager([pass_a, pass_b])
    assert pm.names == ("pass-a", "pass-b")


def test_pass_manager_duplicate_names_raises() -> None:
    pass_a = _FunctionPass("pass-a", lambda fn: fn)
    pass_dup = _FunctionPass("pass-a", lambda fn: fn)
    with pytest.raises(ValueError, match="duplicate pass name"):
        _PassManager([pass_a, pass_dup])


def test_pass_manager_execution_order() -> None:
    order: list[str] = []

    def run_1(fn: IRFunction) -> IRFunction:
        order.append("pass1")
        return fn

    def run_2(fn: IRFunction) -> IRFunction:
        order.append("pass2")
        return fn

    pm = _PassManager(
        [
            _FunctionPass("p1", run_1),
            _FunctionPass("p2", run_2),
        ]
    )
    result = compile_source(
        "fn main() -> tryte:\n    return 0\n",
        mode=SyntaxMode.V0_6,
    )
    pm.run(result.ir)
    assert order == ["pass1", "pass2"]
