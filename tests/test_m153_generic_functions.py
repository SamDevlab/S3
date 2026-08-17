from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.pipeline import compile_source, run_source


def test_scalar_generic_function_is_explicitly_specialized_and_runs_o0_o1() -> None:
    source = (
        "fn identity<T: scalar>(value: T) -> T:\n"
        "    return value\n"
        "fn main() -> i64:\n"
        "    return identity<i64>(7)\n"
    )

    compilation = compile_source(source, optimization="O0")
    assert [function.name for function in compilation.ast.functions] == [
        "main",
        "__s3_generic__identity__i64",
    ]
    assert run_source(source, optimization="O0") == 7
    assert run_source(source, optimization="O1") == 7


def test_owned_generic_function_preserves_composite_value_flow() -> None:
    source = (
        "fn forward<T: owned>(value: T) -> T:\n"
        "    return value\n"
        "fn main() -> i64:\n"
        '    value: text = text_from_static("hello")\n'
        "    result: text = forward<text>(value)\n"
        "    return text_len(&result)\n"
    )

    assert run_source(source, optimization="O0") == 5
    assert run_source(source, optimization="O1") == 5


def test_generic_specialization_identity_is_deterministic() -> None:
    source = (
        "fn identity<T: scalar>(value: T) -> T:\n"
        "    return value\n"
        "fn main() -> i64:\n"
        "    return identity<i64>(7)\n"
    )

    first = compile_source(source, optimization="O0")
    second = compile_source(source, optimization="O0")
    assert first.ast == second.ast
    assert first.ir == second.ir
    assert first.assembly_text == second.assembly_text


def test_generic_constraint_rejects_an_incompatible_type_argument() -> None:
    source = (
        "fn forward<T: owned>(value: T) -> T:\n"
        "    return value\n"
        "fn main() -> i64:\n"
        "    return forward<tryte>(7)\n"
    )

    with pytest.raises(SemanticError) as error:
        compile_source(source)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE


def test_generic_calls_require_explicit_type_arguments() -> None:
    source = (
        "fn identity<T: scalar>(value: T) -> T:\n"
        "    return value\n"
        "fn main() -> i64:\n"
        "    return identity(7)\n"
    )

    with pytest.raises(SemanticError, match="requires explicit type arguments"):
        compile_source(source)
