from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import ParseError, parse


def test_parser_accepts_enum_payload_fields_and_preserves_empty_variants() -> None:
    program = parse(
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Text(value: string)\n"
        "    Empty\n"
        "fn main() -> tryte:\n"
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    )

    enum = program.enums[0]
    assert [variant.name for variant in enum.variants] == ["Ok", "Text", "Empty"]
    assert [
        (field.name, field.type_name)
        for field in enum.variants[0].payload_fields
    ] == [("value", ast.TypeName.TRYTE)]
    assert enum.variants[1].payload_fields[0].type_name is ast.TypeName.STRING
    assert enum.variants[2].payload_fields == ()


def test_parser_accepts_local_and_qualified_enum_payload_construction() -> None:
    program = parse(
        "fn main() -> tryte:\n"
        "    local: Result = Result.Ok(value=1)\n"
        "    qualified: api.Result = api.Result.Err(code=2, detail=3)\n"
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    )

    statements = program.functions[0].body.statements
    local = statements[0]
    qualified = statements[1]
    assert isinstance(local, ast.VariableDeclaration)
    assert isinstance(local.initializer, ast.RecordExpression)
    assert local.initializer.type_name == "Result.Ok"
    assert [field.name for field in local.initializer.fields] == ["value"]
    assert isinstance(qualified, ast.VariableDeclaration)
    assert isinstance(qualified.initializer, ast.RecordExpression)
    assert qualified.initializer.type_name == "api.Result.Err"
    assert [field.name for field in qualified.initializer.fields] == [
        "code",
        "detail",
    ]


def test_parser_accepts_match_payload_bindings() -> None:
    program = parse(
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Err(code: tryte, detail: tryte)\n"
        "fn inspect(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Ok(value):\n"
        "            return value\n"
        "        Result.Err(code, detail):\n"
        "            return code + detail\n"
        "fn main() -> tryte:\n"
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    )

    cases = program.functions[0].body.statements[0].cases
    assert isinstance(cases[0].label, ast.MatchPayloadLabel)
    assert cases[0].label.bindings == ("value",)
    assert isinstance(cases[1].label, ast.MatchPayloadLabel)
    assert cases[1].label.bindings == ("code", "detail")


@pytest.mark.parametrize(
    "source",
    (
        "enum Result:\n"
        "    Ok()\n"
        "fn main() -> tryte:\n"
        "    return 0\n",
        "enum Result:\n"
        "    Ok(value: tryte,)\n"
        "fn main() -> tryte:\n"
        "    return 0\n",
        "enum Result:\n"
        "    Ok(value tryte)\n"
        "fn main() -> tryte:\n"
        "    return 0\n",
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "fn main() -> tryte:\n"
        "    value: Result = Result.Ok(value=1)\n"
        "    match value:\n"
        "        Result.Ok():\n"
        "            return 1\n",
    ),
)
def test_parser_rejects_invalid_payload_syntax(source: str) -> None:
    with pytest.raises(ParseError):
        parse(source, mode=SyntaxMode.V0_6)
