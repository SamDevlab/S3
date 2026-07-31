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


def test_exhaustive_enum_match_statement_runs_in_hosted_o0_and_o1() -> None:
    source = (
        "enum Sign:\n"
        "    Negative\n"
        "    Zero\n"
        "    Positive\n"
        "fn main() -> tryte:\n"
        "    value: Sign = Sign.Positive\n"
        "    match value:\n"
        "        Sign.Negative:\n"
        "            return -1\n"
        "        Sign.Zero:\n"
        "            return 0\n"
        "        Sign.Positive:\n"
        "            return 1\n"
    )

    assert run_source(source, optimization="O0") == 1
    assert run_source(source, optimization="O1") == 1


def test_enum_match_expression_runs_in_hosted_o0_and_o1() -> None:
    source = (
        "enum Sign:\n"
        "    Negative\n"
        "    Zero\n"
        "    Positive\n"
        "fn main() -> tryte:\n"
        "    value: Sign = Sign.Negative\n"
        "    return match value:\n"
        "        Sign.Negative: -1\n"
        "        Sign.Zero: 0\n"
        "        Sign.Positive: 1\n"
    )

    assert run_source(source, optimization="O0") == -1
    assert run_source(source, optimization="O1") == -1


def test_enum_match_fallback_covers_missing_variants() -> None:
    source = (
        "enum Sign:\n"
        "    Negative\n"
        "    Zero\n"
        "    Positive\n"
        "fn main() -> tryte:\n"
        "    value: Sign = Sign.Zero\n"
        "    match value:\n"
        "        Sign.Negative:\n"
        "            return -1\n"
        "        else:\n"
        "            return 1\n"
    )

    assert run_source(source, optimization="O0") == 1
    assert run_source(source, optimization="O1") == 1


def test_enum_match_supports_more_than_three_variants() -> None:
    source = (
        "enum Opcode:\n"
        "    Add\n"
        "    Subtract\n"
        "    Minimum\n"
        "    Maximum\n"
        "fn main() -> tryte:\n"
        "    value: Opcode = Opcode.Maximum\n"
        "    match value:\n"
        "        Opcode.Add:\n"
        "            return 0\n"
        "        Opcode.Subtract:\n"
        "            return 1\n"
        "        Opcode.Minimum:\n"
        "            return 2\n"
        "        Opcode.Maximum:\n"
        "            return 3\n"
    )

    assert run_source(source, optimization="O0") == 3
    assert run_source(source, optimization="O1") == 3


def test_enum_match_rejects_missing_and_duplicate_arms() -> None:
    with pytest.raises(SemanticError) as missing:
        compile_source(
            "enum Sign:\n"
            "    Negative\n"
            "    Zero\n"
            "fn main() -> tryte:\n"
            "    value: Sign = Sign.Negative\n"
            "    match value:\n"
            "        Sign.Negative:\n"
            "            return -1\n"
        )
    assert _semantic_code(missing) is DiagnosticCode.MATCH_NON_EXHAUSTIVE

    with pytest.raises(SemanticError) as duplicate:
        compile_source(
            "enum Sign:\n"
            "    Negative\n"
            "    Zero\n"
            "fn main() -> tryte:\n"
            "    value: Sign = Sign.Negative\n"
            "    match value:\n"
            "        Sign.Negative:\n"
            "            return -1\n"
            "        Sign.Negative:\n"
            "            return 0\n"
            "        Sign.Zero:\n"
            "            return 1\n"
        )
    assert _semantic_code(duplicate) is DiagnosticCode.MATCH_DUPLICATE_ARM


def test_enum_match_rejects_arms_from_another_enum() -> None:
    with pytest.raises(SemanticError) as incompatible:
        compile_source(
            "enum Sign:\n"
            "    Negative\n"
            "enum Other:\n"
            "    Negative\n"
            "fn main() -> tryte:\n"
            "    value: Sign = Sign.Negative\n"
            "    match value:\n"
            "        Other.Negative:\n"
            "            return -1\n"
        )
    assert _semantic_code(incompatible) is DiagnosticCode.SEMANTIC_TYPE_MISMATCH
