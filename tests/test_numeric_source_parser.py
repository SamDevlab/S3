from __future__ import annotations

from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode, TokenKind, tokenize
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.lowering import lower


def test_lexer_distinguishes_numeric_keywords_and_float_literals() -> None:
    tokens = tokenize("i64 f64 12 0.5", mode=SyntaxMode.V0_6)
    assert [token.kind for token in tokens[:4]] == [
        TokenKind.I64,
        TokenKind.F64,
        TokenKind.INTEGER,
        TokenKind.FLOAT,
    ]


def test_parser_accepts_i64_and_f64_types_and_literals() -> None:
    program = parse(
        "fn main() -> f64:\n"
        "    value: f64 = 0.5\n"
        "    return value\n",
        mode=SyntaxMode.V0_6,
    )
    function = program.functions[0]
    assert function.return_type is ast.TypeName.F64
    declaration = function.body.statements[0]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert declaration.type_name is ast.TypeName.F64
    assert isinstance(declaration.initializer, ast.FloatLiteral)
    assert declaration.initializer.value == 0.5


def test_semantic_model_records_f64_literal_type() -> None:
    program = parse(
        "fn main() -> f64:\n"
        "    value: f64 = 0.5\n"
        "    return value\n",
        mode=SyntaxMode.V0_6,
    )
    model = analyze(program)
    initializer = program.functions[0].body.statements[0].initializer
    assert model.declared_type_of(initializer) is ast.TypeName.F64


def test_numeric_addition_lowers_and_executes_end_to_end() -> None:
    program = parse(
        "fn main() -> f64:\n"
        "    return 0.5 + 0.25\n",
        mode=SyntaxMode.V0_6,
    )
    assert execute_ir(lower(program, analyze(program))) == 0.75
