from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from inspect import Parameter, signature

import pytest

from bootstrap.s3.compilation_context import CompilationContext
from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.optimizer import OptimizationLevel, instruction_count
from bootstrap.s3.pipeline import (
    _compile_source_with_context,
    compile_source,
    run_source,
)


SOURCE_V0_6 = "fn main() -> tryte:\n    return 6\n"
SOURCE_V0_5 = "fn main() -> tryte {\n    return 6;\n}\n"


def test_compilation_context_is_small_immutable_compile_state() -> None:
    context = CompilationContext(optimization="O1", mode=SyntaxMode.V0_6)

    assert tuple(field.name for field in fields(context)) == (
        "optimization",
        "mode",
    )
    assert context.optimization == "O1"
    assert context.mode is SyntaxMode.V0_6
    assert not hasattr(context, "__dict__")

    with pytest.raises(FrozenInstanceError):
        context.mode = SyntaxMode.V0_5  # type: ignore[misc]


def test_compile_source_signature_remains_compatible() -> None:
    parameters = signature(compile_source).parameters

    assert tuple(parameters) == ("source", "optimization", "mode")
    assert parameters["optimization"].default is OptimizationLevel.O0
    assert parameters["mode"].kind is Parameter.KEYWORD_ONLY
    assert parameters["mode"].default is SyntaxMode.V0_6

    compilation = compile_source(SOURCE_V0_6, OptimizationLevel.O0)
    assert Emulator().execute(compilation.assembly) == 6


def test_context_route_preserves_default_o0_v0_6_ir_and_assembly() -> None:
    public = compile_source(SOURCE_V0_6)
    contextual = _compile_source_with_context(
        SOURCE_V0_6,
        CompilationContext(),
    )

    assert contextual.ast == public.ast
    assert contextual.ir == public.ir
    assert contextual.assembly.render() == public.assembly.render()


def test_context_route_preserves_explicit_v0_5() -> None:
    compilation = _compile_source_with_context(
        SOURCE_V0_5,
        CompilationContext(mode=SyntaxMode.V0_5),
    )

    assert compilation.ast.functions[0].name == "main"
    assert Emulator().execute(compilation.assembly) == 6
    assert run_source(SOURCE_V0_5, mode=SyntaxMode.V0_5) == 6


def test_context_route_preserves_o0_and_o1_behavior() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    unused: tryte = 10 + 20\n"
        "    folded: tryte = (1 + 2) & 4\n"
        "    return folded | 5\n"
    )

    o0 = _compile_source_with_context(
        source,
        CompilationContext(optimization=OptimizationLevel.O0),
    )
    o1 = _compile_source_with_context(
        source,
        CompilationContext(optimization="O1"),
    )

    assert Emulator().execute(o0.assembly) == 12
    assert Emulator().execute(o1.assembly) == 12
    assert instruction_count(o1.ir) < instruction_count(o0.ir)
    assert compile_source(source, "O1").assembly.render() == o1.assembly.render()


def test_context_compilations_do_not_share_mutable_state() -> None:
    context = CompilationContext(optimization="O1", mode=SyntaxMode.V0_6)
    first = _compile_source_with_context(
        "fn main() -> tryte:\n    return 1\n",
        context,
    )
    second = _compile_source_with_context(
        "fn main() -> tryte:\n    return 2\n",
        context,
    )

    assert Emulator().execute(first.assembly) == 1
    assert Emulator().execute(second.assembly) == 2
    assert first.tokens != second.tokens
    assert first.assembly.render() != second.assembly.render()


def test_invalid_optimization_keeps_previous_public_behavior() -> None:
    with pytest.raises(ValueError, match="unsupported optimization level 'O9'"):
        compile_source(SOURCE_V0_6, "O9")

    with pytest.raises(ParseError, match="expected expression"):
        compile_source("fn main() -> tryte:\n    return\n", "O9")

    with pytest.raises(AttributeError, match="upper"):
        compile_source(SOURCE_V0_6, object())


def test_invalid_mode_keeps_previous_public_behavior() -> None:
    with pytest.raises(ParseError, match=r"expected '\{'; found ':'"):
        compile_source(SOURCE_V0_6, mode="0.6")  # type: ignore[arg-type]
