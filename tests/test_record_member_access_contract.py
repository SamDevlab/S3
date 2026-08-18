from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
    ParseError,
    SemanticError,
    diagnostic_from_exception,
)
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.pipeline import compile_source, compile_sources, run_source


def _assert_semantic_rejection(
    source: str,
    message: str,
    code: DiagnosticCode = DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
) -> None:
    with pytest.raises(SemanticError) as captured:
        compile_source(source)

    diagnostic = diagnostic_from_exception(captured.value)
    assert diagnostic.phase is DiagnosticPhase.SEMANTIC
    assert diagnostic.category is DiagnosticCategory.SEMANTIC
    assert diagnostic.code is code
    assert diagnostic.message == message


def _assert_sources_semantic_rejection(
    sources: dict[str, str],
    message: str,
    code: DiagnosticCode = DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
) -> None:
    with pytest.raises(SemanticError) as captured:
        compile_sources(sources)

    diagnostic = diagnostic_from_exception(captured.value)
    assert diagnostic.phase is DiagnosticPhase.SEMANTIC
    assert diagnostic.category is DiagnosticCategory.SEMANTIC
    assert diagnostic.code is code
    assert diagnostic.message == message


def test_record_member_access_reads_literal_variable_parameter_and_return_value() -> None:
    source = (
        "record Pair:\n"
        "    left: tryte\n"
        "    right: tryte\n"
        "record Box:\n"
        "    value: tryte\n"
        "fn keep(value: tryte) -> tryte:\n"
        "    return value\n"
        "fn pick(pair: Pair) -> tryte:\n"
        "    return keep(pair.right)\n"
        "fn make() -> Box:\n"
        "    return Box(value=8)\n"
        "fn main() -> tryte:\n"
        "    pair: Pair = Pair(left=3, right=5)\n"
        "    return Box(value=2).value + pair.left + pick(pair) + make().value\n"
    )

    assert run_source(source, optimization="O0") == 18
    assert run_source(source, optimization="O1") == 18


def test_record_member_access_composes_with_enum_match_and_loop_condition() -> None:
    source = (
        "enum Sign:\n"
        "    Negative\n"
        "    Zero\n"
        "    Positive\n"
        "record Tagged:\n"
        "    flag: trit\n"
        "    sign: Sign\n"
        "    value: tryte\n"
        "fn score(item: Tagged) -> tryte:\n"
        "    while item.flag:\n"
        "        return -7\n"
        "    match item.sign:\n"
        "        Sign.Negative:\n"
        "            return -1\n"
        "        Sign.Zero:\n"
        "            return 0\n"
        "        Sign.Positive:\n"
        "            return item.value\n"
        "fn main() -> tryte:\n"
        "    item: Tagged = Tagged(flag=0, sign=Sign.Positive, value=11)\n"
        "    return score(item)\n"
    )

    assert run_source(source, optimization="O0") == 11
    assert run_source(source, optimization="O1") == 11


def test_record_member_access_after_qualified_single_field_record_call() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from maker import make\n"
            "fn main() -> tryte:\n"
            "    return maker.make().value\n"
        ),
        "maker.s3": (
            "module maker\n"
            "record Box:\n"
            "    value: tryte\n"
            "export fn make() -> Box:\n"
            "    return Box(value=7)\n"
        ),
    }

    for optimization in ("O0", "O1"):
        compilation = compile_sources(sources, optimization)
        assert execute_assembly(compilation.assembly) == 7


@pytest.mark.parametrize(
    ("source", "message", "code"),
    (
        (
            "record Box:\n"
            "    value: tryte\n"
            "fn main() -> tryte:\n"
            "    return Box.missing\n",
            "type 'Box' cannot be used as a value",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "fn helper() -> tryte:\n"
            "    return 1\n"
            "fn main() -> tryte:\n"
            "    return helper.value\n",
            "function 'helper' cannot be used as a value",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "fn main() -> tryte:\n"
            "    value: tryte = 1\n"
            "    return value.member\n",
            "field access requires a record value",
            DiagnosticCode.RECORD_FIELD_UNKNOWN,
        ),
        (
            "fn main() -> tryte:\n"
            "    values: tryte[1] = [1]\n"
            "    return values.member\n",
            "field access requires a record value",
            DiagnosticCode.RECORD_FIELD_UNKNOWN,
        ),
        (
            "fn main() -> tryte:\n"
            "    values: tryte[1] = [1]\n"
            "    return values[0].member\n",
            "field access requires a record value",
            DiagnosticCode.RECORD_FIELD_UNKNOWN,
        ),
        (
            "enum Sign:\n"
            "    Negative\n"
            "    Positive\n"
            "fn main() -> tryte:\n"
            "    return Sign.Positive.member\n",
            "field access requires a record value",
            DiagnosticCode.RECORD_FIELD_UNKNOWN,
        ),
        (
            "record Box:\n"
            "    value: tryte\n"
            "fn main() -> tryte:\n"
            "    box: Box = Box(value=1)\n"
            "    return box.missing\n",
            "record 'Box' has no field 'missing'",
            DiagnosticCode.RECORD_FIELD_UNKNOWN,
        ),
    ),
)
def test_record_member_access_rejects_non_record_and_unknown_member_shapes(
    source: str,
    message: str,
    code: DiagnosticCode,
) -> None:
    _assert_semantic_rejection(source, message, code)


def test_record_member_access_rejects_member_assignment_target() -> None:
    with pytest.raises(
        SemanticError,
        match="owned field replacement requires a mutable aggregate",
    ):
        compile_source(
            "record Box:\n"
            "    value: tryte\n"
            "fn main() -> tryte:\n"
            "    box: Box = Box(value=1)\n"
            "    box.value = 2\n"
            "    return box.value\n"
        )


def test_qualified_function_symbol_member_is_rejected_as_non_value() -> None:
    _assert_sources_semantic_rejection(
        {
            "main.s3": (
                "module main\n"
                "from math import inc\n"
                "fn main() -> tryte:\n"
                "    return math.inc.value\n"
            ),
            "math.s3": (
                "module math\n"
                "export fn inc() -> tryte:\n"
                "    return 1\n"
            ),
        },
        "function 'math.inc' cannot be used as a value",
    )
