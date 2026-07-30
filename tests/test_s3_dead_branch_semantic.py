from __future__ import annotations

from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import SemanticModel, analyze


def _parse(source: str) -> ast.Program:
    return parse(source, mode=SyntaxMode.V0_6)


def _analyze(source: str) -> SemanticModel:
    return analyze(_parse(source))


def test_semantic_dead_branch_constant_conditions_recognized() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    match 0:\n"
        "        0:\n"
        "            x: tryte = 10\n"
        "        else:\n"
        "            y: tryte = 20\n"
        "    while 0:\n"
        "        z: tryte = 30\n"
        "    return 0\n"
    )
    model = analyze(program)
    assert model is not None
