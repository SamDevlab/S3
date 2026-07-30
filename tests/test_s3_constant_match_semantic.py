from __future__ import annotations

from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import SemanticModel, analyze


def _parse(source: str) -> ast.Program:
    return parse(source, mode=SyntaxMode.V0_6)


def _analyze(source: str) -> SemanticModel:
    return analyze(_parse(source))


def test_semantic_constant_match_statement() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    match 0:\n"
        "        -1:\n"
        "            x: tryte = 10\n"
        "        0:\n"
        "            y: tryte = 20\n"
        "        else:\n"
        "            z: tryte = 30\n"
        "    return 0\n"
    )
    model = analyze(program)
    assert model is not None


def test_semantic_constant_match_expression() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    res: tryte = match 1:\n"
        "        -1: 100\n"
        "        0: 200\n"
        "        1: 300\n"
        "    return res\n"
    )
    model = analyze(program)
    decl = program.functions[0].body.statements[0]
    assert isinstance(decl, ast.VariableDeclaration)
    assert model.constant_value_of(decl.initializer) == 300
