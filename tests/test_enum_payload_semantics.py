from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.lexer import SyntaxMode, tokenize
from bootstrap.s3.module_compilation import prepare_module_compilation
from bootstrap.s3.parser import parse_tokens
from bootstrap.s3.semantic import SemanticModel, analyze


def _semantic_model(source: str) -> SemanticModel:
    return analyze(
        parse_tokens(
            tokenize(source, mode=SyntaxMode.V0_6),
            mode=SyntaxMode.V0_6,
        )
    )


def _semantic_error(source: str) -> SemanticError:
    with pytest.raises(SemanticError) as error:
        _semantic_model(source)
    return error.value


def test_enum_payload_construction_validates_named_fields_and_types() -> None:
    _semantic_model(
        "record Detail:\n"
        "    code: tryte\n"
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Err(detail: Detail)\n"
        "    Empty\n"
        "fn main() -> tryte:\n"
        "    ok: Result = Result.Ok(value=7)\n"
        "    err: Result = Result.Err(detail=Detail(code=3))\n"
        "    empty: Result = Result.Empty\n"
        "    return 0\n"
    )


@pytest.mark.parametrize(
    ("initializer", "code"),
    (
        ("Result.Pair(left=1)", DiagnosticCode.RECORD_FIELD_MISSING),
        ("Result.Ok(value=1, extra=2)", DiagnosticCode.RECORD_FIELD_UNKNOWN),
        ("Result.Ok(value=1, value=2)", DiagnosticCode.RECORD_FIELD_DUPLICATE),
        ("Result.Ok(value=Flag.On)", DiagnosticCode.SEMANTIC_TYPE_MISMATCH),
        ("Result.Missing(value=1)", DiagnosticCode.ENUM_VARIANT_UNKNOWN),
        ("Result.Empty(value=1)", DiagnosticCode.RECORD_FIELD_UNKNOWN),
    ),
)
def test_enum_payload_construction_rejects_invalid_fields(
    initializer: str,
    code: DiagnosticCode,
) -> None:
    error = _semantic_error(
        "enum Flag:\n"
        "    On\n"
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Pair(left: tryte, right: tryte)\n"
        "    Empty\n"
        "fn main() -> tryte:\n"
        f"    value: Result = {initializer}\n"
        "    return 0\n"
    )

    assert error.diagnostic_code is code


def test_enum_payload_construction_rejects_nominal_mismatch() -> None:
    error = _semantic_error(
        "record Left:\n"
        "    value: tryte\n"
        "record Right:\n"
        "    value: tryte\n"
        "enum Result:\n"
        "    Ok(value: Left)\n"
        "fn main() -> tryte:\n"
        "    value: Result = Result.Ok(value=Right(value=1))\n"
        "    return 0\n"
    )

    assert error.diagnostic_code is DiagnosticCode.SEMANTIC_TYPE_MISMATCH


def test_enum_payload_layout_rejects_incompatible_slot_types() -> None:
    error = _semantic_error(
        "enum Result:\n"
        "    Trit(value: trit)\n"
        "    Tryte(value: tryte)\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    assert error.diagnostic_code is DiagnosticCode.SEMANTIC_TYPE_MISMATCH
    assert "payload slot 1 has incompatible types trit and tryte" in str(error)


def test_enum_payload_match_bindings_are_scoped_to_the_case() -> None:
    _semantic_model(
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Err(code: tryte)\n"
        "fn inspect(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Ok(value):\n"
        "            return value\n"
        "        Result.Err(code):\n"
        "            return code\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    error = _semantic_error(
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Err(code: tryte)\n"
        "fn inspect(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Ok(value):\n"
        "            seen: tryte = value\n"
        "        Result.Err(code):\n"
        "            seen: tryte = code\n"
        "    return value\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )
    assert "undeclared variable 'value'" in str(error)


@pytest.mark.parametrize(
    "label",
    (
        "Result.Ok",
        "Result.Ok(other)",
        "Result.Ok(value, value)",
        "Result.Empty(value)",
    ),
)
def test_enum_payload_match_rejects_invalid_bindings(label: str) -> None:
    error = _semantic_error(
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Empty\n"
        "fn inspect(result: Result) -> tryte:\n"
        "    match result:\n"
        f"        {label}:\n"
        "            return 1\n"
        "        Result.Empty:\n"
        "            return 0\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    assert error.diagnostic_code in {
        DiagnosticCode.RECORD_FIELD_DUPLICATE,
        DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
    }


def test_enum_return_policy_uses_total_enum_width() -> None:
    _semantic_model(
        "enum Sign:\n"
        "    Negative\n"
        "    Positive\n"
        "fn choose(value: Sign) -> Sign:\n"
        "    return value\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    error = _semantic_error(
        "enum Result:\n"
        "    Empty\n"
        "    Ok(value: tryte)\n"
        "fn choose(value: Result) -> Result:\n"
        "    return value\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )
    assert error.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_RETURN_TYPE
    assert "multi-cell enum returns require a future aggregate ABI" in str(error)


def test_imported_enum_payload_construction_and_match_are_semantic_values() -> None:
    plan = prepare_module_compilation(
        {
            "main.s3": (
                "module main\n"
                "from api import Result\n"
                "fn inspect(result: Result) -> tryte:\n"
                "    match result:\n"
                "        Result.Ok(value):\n"
                "            return value\n"
                "        Result.Empty:\n"
                "            return 0\n"
                "fn main() -> tryte:\n"
                "    value: Result = api.Result.Ok(value=4)\n"
                "    return 0\n"
            ),
            "api.s3": (
                "module api\n"
                "export enum Result:\n"
                "    Empty\n"
                "    Ok(value: tryte)\n"
                "export fn marker() -> tryte:\n"
                "    return 0\n"
            ),
        }
    )

    model = analyze(plan.program)
    assert "__s3mod_api__type_Result" in model.enums
