from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRModule,
    IROpcode,
    IRRegister,
    IRType,
)
from bootstrap.s3.optimizer import OptimizationLevel, _o1_passes, optimize_ir
from bootstrap.s3.passes import _PassManager
from bootstrap.s3.pipeline import compile_source


ROOT = Path(__file__).parents[1]


def _function(name: str) -> IRFunction:
    return IRFunction(
        name,
        (),
        IRType.TRYTE,
        (IRRegister(0, IRType.TRYTE),),
        (
            IRBasicBlock(
                "entry",
                (
                    IRInstruction(
                        IROpcode.CONST,
                        result=0,
                        immediate=6,
                    ),
                    IRInstruction(IROpcode.RETURN, operands=(0,)),
                ),
            ),
        ),
    )


def _module(*names: str) -> IRModule:
    if not names:
        names = ("main",)
    return IRModule(tuple(_function(name) for name in names))


@dataclass(frozen=True, slots=True)
class _RecordingPass:
    name: str
    events: list[str]

    def run_function(self, function: IRFunction) -> IRFunction:
        self.events.append(f"{function.name}/{self.name}")
        return function


class _SentinelError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _FailingPass:
    name: str = "failing"

    def run_function(self, function: IRFunction) -> IRFunction:
        del function
        raise _SentinelError("pass failed")


def test_pass_manager_runs_passes_in_explicit_order() -> None:
    events: list[str] = []
    manager = _PassManager(
        (
            _RecordingPass("first", events),
            _RecordingPass("second", events),
        )
    )

    assert manager.names == ("first", "second")
    assert manager.run(_module()) == _module()
    assert events == ["main/first", "main/second"]


def test_pass_manager_runs_function_major_not_pass_major() -> None:
    events: list[str] = []
    manager = _PassManager(
        (
            _RecordingPass("first", events),
            _RecordingPass("second", events),
        )
    )

    assert manager.run(_module("function-a", "function-b")) == _module(
        "function-a",
        "function-b",
    )
    assert events == [
        "function-a/first",
        "function-a/second",
        "function-b/first",
        "function-b/second",
    ]


def test_pass_manager_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError, match="duplicate pass name"):
        _PassManager(
            (
                _RecordingPass("same", []),
                _RecordingPass("same", []),
            )
        )


def test_empty_pass_manager_is_valid_for_o0_shape() -> None:
    module = _module()

    assert _PassManager().names == ()
    assert _PassManager().run(module) is module


def test_pass_errors_are_not_wrapped() -> None:
    with pytest.raises(_SentinelError, match="pass failed"):
        _PassManager((_FailingPass(),)).run(_module())


def test_o1_pass_order_is_explicit_and_stable() -> None:
    assert tuple(pass_.name for pass_ in _o1_passes()) == (
        "remove-unreachable-blocks",
        "thread-empty-jumps",
        "ssa-optimizations",
        "fold-constants",
        "eliminate-dead-pure-instructions",
        "bounded-vector-bounds-elimination",
    )



def test_optimize_ir_o0_preserves_existing_identity_and_assembly() -> None:
    module = compile_source(
        "fn main() -> tryte:\n    return 1 + 2\n",
        OptimizationLevel.O0,
    ).ir

    assert optimize_ir(module, OptimizationLevel.O0) is module
    assert generate_assembly(optimize_ir(module, "O0")) == generate_assembly(module)


def test_optimize_ir_o1_preserves_public_artifacts() -> None:
    source = (ROOT / "examples" / "static_array.s3").read_text(encoding="utf-8")

    direct = optimize_ir(compile_source(source, "O0").ir, "O1")
    compiled = compile_source(source, "O1").ir

    assert direct == compiled
    assert generate_assembly(direct).render() == compile_source(
        source,
        "O1",
    ).assembly.render()


def test_pass_manager_leaves_no_residual_state_between_runs() -> None:
    first = optimize_ir(
        compile_source("fn main() -> tryte:\n    return 1 + 2\n", "O0").ir,
        "O1",
    )
    second = optimize_ir(
        compile_source("fn main() -> tryte:\n    return 2 + 3\n", "O0").ir,
        "O1",
    )

    assert first != second
    assert generate_assembly(first).render() != generate_assembly(second).render()
