from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.pipeline import compile_source, run_source


def _semantic_code(error: pytest.ExceptionInfo[SemanticError]) -> DiagnosticCode:
    return error.value.diagnostic_code


def test_parser_accepts_enum_declaration_and_qualified_variant() -> None:
    program = parse(
        "enum Sign:\n"
        "    Negative\n"
        "    Zero\n"
        "    Positive\n"
        "fn main() -> tryte:\n"
        "    value: Sign = Sign.Positive\n"
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    )

    assert program.enums[0].name == "Sign"
    assert [variant.name for variant in program.enums[0].variants] == [
        "Negative",
        "Zero",
        "Positive",
    ]


def test_enum_discriminant_runs_in_hosted_o0_and_o1() -> None:
    source = (
        "enum Sign:\n"
        "    Negative\n"
        "    Zero\n"
        "    Positive\n"
        "fn main() -> Sign:\n"
        "    value: Sign = Sign.Positive\n"
        "    return value\n"
    )

    assert run_source(source, optimization="O0") == 2
    assert run_source(source, optimization="O1") == 2
    compilation = compile_source(source, "O1")
    assert compilation.semantic_model.enum("Sign").discriminant("Positive") == 2


def test_enum_can_flow_through_parameters_and_returns() -> None:
    source = (
        "enum Sign:\n"
        "    Negative\n"
        "    Zero\n"
        "    Positive\n"
        "fn choose(value: Sign) -> Sign:\n"
        "    return value\n"
        "fn main() -> Sign:\n"
        "    value: Sign = choose(Sign.Zero)\n"
        "    return value\n"
    )

    assert run_source(source, optimization="O0") == 1
    assert run_source(source, optimization="O1") == 1


def test_enum_equality_and_inequality_return_trit() -> None:
    equal_source = (
        "enum Sign:\n"
        "    Negative\n"
        "    Zero\n"
        "    Positive\n"
        "fn main() -> trit:\n"
        "    return Sign.Negative == Sign.Negative\n"
    )
    not_equal_source = (
        "enum Sign:\n"
        "    Negative\n"
        "    Zero\n"
        "    Positive\n"
        "fn main() -> trit:\n"
        "    return Sign.Negative != Sign.Positive\n"
    )

    assert run_source(equal_source, optimization="O0") == -1
    assert run_source(equal_source, optimization="O1") == -1
    assert run_source(not_equal_source, optimization="O0") == -1
    assert run_source(not_equal_source, optimization="O1") == -1


def test_enum_rejects_duplicate_unknown_and_incompatible_variants() -> None:
    with pytest.raises(SemanticError) as duplicate:
        compile_source(
            "enum Sign:\n"
            "    Negative\n"
            "    Negative\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )
    assert _semantic_code(duplicate) is DiagnosticCode.ENUM_VARIANT_DUPLICATE

    with pytest.raises(SemanticError) as unknown:
        compile_source(
            "enum Sign:\n"
            "    Negative\n"
            "fn main() -> tryte:\n"
            "    value: Sign = Sign.Positive\n"
            "    return value\n"
        )
    assert _semantic_code(unknown) is DiagnosticCode.ENUM_VARIANT_UNKNOWN

    with pytest.raises(SemanticError) as incompatible:
        compile_source(
            "enum Sign:\n"
            "    Negative\n"
            "enum Other:\n"
            "    Negative\n"
            "fn main() -> trit:\n"
            "    return Sign.Negative == Other.Negative\n"
        )
    assert _semantic_code(incompatible) is DiagnosticCode.SEMANTIC_TYPE_MISMATCH


def test_enum_rejects_ordering_operator() -> None:
    with pytest.raises(SemanticError, match="enum values"):
        compile_source(
            "enum Sign:\n"
            "    Negative\n"
            "    Zero\n"
            "fn main() -> trit:\n"
            "    return Sign.Negative < Sign.Zero\n"
        )
