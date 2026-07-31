from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.pipeline import compile_source, run_source


def _semantic_code(error: pytest.ExceptionInfo[SemanticError]) -> DiagnosticCode:
    return error.value.diagnostic_code


def test_parser_accepts_record_declaration_literal_and_field_access() -> None:
    program = parse(
        "record Pair:\n"
        "    left: tryte\n"
        "    right: trit\n"
        "fn main() -> tryte:\n"
        "    pair: Pair = Pair(left=7, right=-1)\n"
        "    return pair.left\n",
        mode=SyntaxMode.V0_6,
    )

    assert program.records[0].name == "Pair"
    assert [field.name for field in program.records[0].fields] == [
        "left",
        "right",
    ]


def test_record_field_access_runs_in_hosted_o0_and_o1() -> None:
    source = (
        "record Pair:\n"
        "    left: tryte\n"
        "    right: tryte\n"
        "fn main() -> tryte:\n"
        "    pair: Pair = Pair(left=7, right=5)\n"
        "    return pair.left + pair.right\n"
    )

    assert run_source(source, optimization="O0") == 12
    assert run_source(source, optimization="O1") == 12
    compilation = compile_source(source, "O1")
    assert compilation.ir.functions[0].name == "main"


def test_record_field_literal_can_be_accessed_directly() -> None:
    source = (
        "record Box:\n"
        "    value: tryte\n"
        "fn main() -> tryte:\n"
        "    return Box(value=9).value\n"
    )

    assert run_source(source) == 9


def test_record_parameter_is_flattened_in_declared_field_order() -> None:
    source = (
        "record Pair:\n"
        "    left: tryte\n"
        "    right: tryte\n"
        "fn sum(pair: Pair) -> tryte:\n"
        "    return pair.left + pair.right\n"
        "fn main() -> tryte:\n"
        "    pair: Pair = Pair(left=7, right=5)\n"
        "    return sum(pair)\n"
    )

    assert run_source(source, optimization="O0") == 12
    assert run_source(source, optimization="O1") == 12


def test_record_literal_can_be_passed_as_flattened_argument() -> None:
    source = (
        "record Pair:\n"
        "    left: tryte\n"
        "    right: tryte\n"
        "fn sum(pair: Pair) -> tryte:\n"
        "    return pair.left + pair.right\n"
        "fn main() -> tryte:\n"
        "    return sum(Pair(left=4, right=6))\n"
    )

    assert run_source(source, optimization="O0") == 10
    assert run_source(source, optimization="O1") == 10


def test_single_field_record_return_uses_scalar_result_register() -> None:
    source = (
        "record Box:\n"
        "    value: tryte\n"
        "fn make() -> Box:\n"
        "    return Box(value=9)\n"
        "fn main() -> tryte:\n"
        "    box: Box = make()\n"
        "    return box.value\n"
    )

    assert run_source(source, optimization="O0") == 9
    assert run_source(source, optimization="O1") == 9


def test_single_field_record_return_can_be_accessed_directly() -> None:
    source = (
        "record Box:\n"
        "    value: tryte\n"
        "fn make() -> Box:\n"
        "    return Box(value=8)\n"
        "fn main() -> tryte:\n"
        "    return make().value\n"
    )

    assert run_source(source, optimization="O0") == 8
    assert run_source(source, optimization="O1") == 8


def test_record_field_can_store_enum_value() -> None:
    source = (
        "enum Sign:\n"
        "    Negative\n"
        "    Zero\n"
        "    Positive\n"
        "record Tagged:\n"
        "    sign: Sign\n"
        "    value: tryte\n"
        "fn main() -> tryte:\n"
        "    item: Tagged = Tagged(sign=Sign.Positive, value=11)\n"
        "    match item.sign:\n"
        "        Sign.Negative:\n"
        "            return -1\n"
        "        Sign.Zero:\n"
        "            return 0\n"
        "        Sign.Positive:\n"
        "            return item.value\n"
    )

    assert run_source(source, optimization="O0") == 11
    assert run_source(source, optimization="O1") == 11


def test_record_rejects_duplicate_missing_and_unknown_fields() -> None:
    with pytest.raises(SemanticError) as duplicate:
        compile_source(
            "record Pair:\n"
            "    left: tryte\n"
            "    left: tryte\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )
    assert _semantic_code(duplicate) is DiagnosticCode.RECORD_FIELD_DUPLICATE

    with pytest.raises(SemanticError) as missing:
        compile_source(
            "record Pair:\n"
            "    left: tryte\n"
            "    right: tryte\n"
            "fn main() -> tryte:\n"
            "    pair: Pair = Pair(left=7)\n"
            "    return pair.left\n"
        )
    assert _semantic_code(missing) is DiagnosticCode.RECORD_FIELD_MISSING

    with pytest.raises(SemanticError) as unknown:
        compile_source(
            "record Pair:\n"
            "    left: tryte\n"
            "fn main() -> tryte:\n"
            "    pair: Pair = Pair(left=7, right=5)\n"
            "    return pair.left\n"
        )
    assert _semantic_code(unknown) is DiagnosticCode.RECORD_FIELD_UNKNOWN


def test_record_return_is_blocked_until_aggregate_abi_exists() -> None:
    with pytest.raises(SemanticError, match="aggregate ABI"):
        compile_source(
            "record Pair:\n"
            "    left: tryte\n"
            "    right: tryte\n"
            "fn make() -> Pair:\n"
            "    return Pair(left=1, right=2)\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )
