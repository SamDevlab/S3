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
            "record Box:\n"
            "    value: tryte\n"
            "fn make() -> Box:\n"
            "    return Box(value=1)\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )
