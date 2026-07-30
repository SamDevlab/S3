from __future__ import annotations

from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import SemanticModel, analyze


def _parse(source: str) -> ast.Program:
    return parse(source, mode=SyntaxMode.V0_6)


def _analyze(source: str) -> SemanticModel:
    return analyze(_parse(source))


def test_semantic_constant_if_condition_evaluation() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    match 1:\n"
        "        1:\n"
        "            x: tryte = 10\n"
        "        else:\n"
        "            y: tryte = 20\n"
        "    return 0\n"
    )
    model = analyze(program)
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, ast.SwitchStatement)
    assert model.constant_value_of(stmt.expression) == 1
