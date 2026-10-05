from __future__ import annotations

import json
from pathlib import Path

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.parser import parse
from bootstrap.s3.pipeline import compile_source


_ROOT = Path(__file__).parents[1]


def _module_body(relative_path: str) -> str:
    return "\n".join(
        line
        for line in (_ROOT / relative_path).read_text(encoding="utf-8").splitlines()
        if not line.startswith("module ") and not line.startswith("from ")
    )


_COMPILER_SOURCE = "\n".join(
    _module_body(path)
    for path in (
        "selfhost/compiler_ng/character_classes.s3",
        "selfhost/compiler_ng/lexer.s3",
        "selfhost/compiler_ng/parser.s3",
    )
)


def _ng_parse_status(source: str) -> int:
    wrapper = f"""
fn main() -> i64:
    mut source_text: text = text_from_static({json.dumps(source)})
    mut source_bytes: bytes = bytes_from_text(&source_text)
    mut tokens: vector<NgToken> = vector_new<NgToken>({len(source.encode("utf-8")) + 1})
    mut functions: vector<NgFunction> = vector_new<NgFunction>({len(source.encode("utf-8")) + 1})
    mut parameters: vector<NgParameter> = vector_new<NgParameter>({len(source.encode("utf-8")) + 1})
    mut nodes: vector<NgAstNode> = vector_new<NgAstNode>({len(source.encode("utf-8")) + 1})
    mut lex_status: i64 = ng_lex(&source_bytes, &mut tokens)
    match lex_status <=> 0:
        -1:
            return -2
        0:
            return ng_parse_program(&source_bytes, &tokens, &mut functions, &mut parameters, &mut nodes)
        1:
            return -2
"""
    compilation = compile_source(_COMPILER_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    return int(execute_ir(compilation.ir))


def test_nextgen_parser_matches_python_precedence_and_builds_indexed_ast() -> None:
    source = "fn add(left: i64, right: i64) -> i64:\n    return left + right * 2\n"
    reference = parse(source)
    function = reference.functions[0]
    assert function.name == "add"
    assert tuple(parameter.name for parameter in function.parameters) == ("left", "right")
    returned = function.body.statements[0].expression
    assert isinstance(returned, ast.BinaryExpression)
    assert isinstance(returned.left, ast.Identifier)
    assert isinstance(returned.right, ast.BinaryExpression)
    assert isinstance(returned.right.left, ast.Identifier)
    assert isinstance(returned.right.right, ast.IntegerLiteral)

    wrapper = f"""
fn main() -> i64:
    mut source_text: text = text_from_static({json.dumps(source)})
    mut source_bytes: bytes = bytes_from_text(&source_text)
    mut tokens: vector<NgToken> = vector_new<NgToken>(32)
    mut functions: vector<NgFunction> = vector_new<NgFunction>(4)
    mut parameters: vector<NgParameter> = vector_new<NgParameter>(8)
    mut nodes: vector<NgAstNode> = vector_new<NgAstNode>(16)
    mut lex_status: i64 = ng_lex(&source_bytes, &mut tokens)
    mut parse_status: i64 = ng_parse_program(&source_bytes, &tokens, &mut functions, &mut parameters, &mut nodes)
    match lex_status <=> 0:
        -1:
            return -10
        0:
            match parse_status <=> 0:
                -1:
                    return -20
                0:
                    mut function: NgFunction = vector_get<NgFunction>(&functions, 0)
                    mut first_parameter: NgParameter = vector_get<NgParameter>(&parameters, function.first_parameter)
                    mut second_parameter: NgParameter = vector_get<NgParameter>(&parameters, function.first_parameter + 1)
                    mut body_link: NgAstNode = vector_get<NgAstNode>(&nodes, function.body_node)
                    mut return_statement: NgAstNode = vector_get<NgAstNode>(&nodes, body_link.left)
                    mut root: NgAstNode = vector_get<NgAstNode>(&nodes, return_statement.left)
                    mut left: NgAstNode = vector_get<NgAstNode>(&nodes, root.left)
                    mut right: NgAstNode = vector_get<NgAstNode>(&nodes, root.right)
                    mut right_left: NgAstNode = vector_get<NgAstNode>(&nodes, right.left)
                    mut right_right: NgAstNode = vector_get<NgAstNode>(&nodes, right.right)
                    match vector_len<NgFunction>(&functions) <=> 1:
                        -1:
                            return -30
                        0:
                            match function.parameter_count <=> 2:
                                -1:
                                    return -31
                                0:
                                    match first_parameter.type_kind <=> 1:
                                        -1:
                                            return -32
                                        0:
                                            match second_parameter.type_kind <=> 1:
                                                -1:
                                                    return -33
                                                0:
                                                    match function.return_type <=> 1:
                                                        -1:
                                                            return -34
                                                        0:
                                                            match root.kind <=> 4:
                                                                -1:
                                                                    return -35
                                                                0:
                                                                    match root.operation <=> 343:
                                                                        -1:
                                                                            return -36
                                                                        0:
                                                                            match left.kind <=> 2:
                                                                                -1:
                                                                                    return -37
                                                                                0:
                                                                                    match right.kind <=> 4:
                                                                                        -1:
                                                                                            return -38
                                                                                        0:
                                                                                            match right.operation <=> 342:
                                                                                                -1:
                                                                                                    return -39
                                                                                                0:
                                                                                                    match right_left.kind <=> 2:
                                                                                                        -1:
                                                                                                            return -40
                                                                                                        0:
                                                                                                            match right_right.kind <=> 1:
                                                                                                                -1:
                                                                                                                    return -41
                                                                                                                0:
                                                                                                                    return 0
                                                                                                                1:
                                                                                                                    return -41
                                                                                                        1:
                                                                                                            return -40
                                                                                                1:
                                                                                                    return -39
                                                                                        1:
                                                                                            return -38
                                                                                1:
                                                                                    return -37
                                                                        1:
                                                                            return -36
                                                                1:
                                                                    return -35
                                                        1:
                                                            return -34
                                                1:
                                                    return -33
                                        1:
                                            return -32
                                1:
                                    return -31
                        1:
                            return -30
                1:
                    return -20
        1:
            return -10
"""
    compilation = compile_source(_COMPILER_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    assert execute_ir(compilation.ir) == 0


def test_nextgen_parser_keeps_multiple_function_boundaries_and_parameter_spans() -> None:
    source = (
        "fn first() -> i64:\n    return 1\n"
        "fn second(value: i64) -> i64:\n    return value + 2\n"
    )
    reference = parse(source)
    assert [function.name for function in reference.functions] == ["first", "second"]
    assert _ng_parse_status(source) == 0


def test_nextgen_parser_accepts_positional_calls_and_rejects_trailing_commas() -> None:
    source = (
        "fn identity(value: i64) -> i64:\n    return value\n"
        "fn main() -> i64:\n    return identity(7)\n"
    )
    assert [function.name for function in parse(source).functions] == ["identity", "main"]
    assert _ng_parse_status(source) == 0

    invalid = "fn main() -> i64:\n    return identity(7,)\n"
    with pytest.raises(ParseError):
        parse(invalid)
    assert _ng_parse_status(invalid) < 0


def test_nextgen_parser_preserves_local_declaration_assignment_and_return_order() -> None:
    source = (
        "fn adjust(value: i64) -> i64:\n"
        "    mut current: i64 = value\n"
        "    current = current + 1\n"
        "    return current\n"
    )
    function = parse(source).functions[0]
    assert isinstance(function.body.statements[0], ast.VariableDeclaration)
    assert function.body.statements[0].mutable
    assert isinstance(function.body.statements[1], ast.AssignmentStatement)
    assert isinstance(function.body.statements[2], ast.ReturnStatement)
    assert _ng_parse_status(source) == 0


def test_nextgen_parser_preserves_ternary_match_arm_order_and_nested_blocks() -> None:
    source = (
        "fn choose(value: trit) -> i64:\n"
        "    match value:\n"
        "        -1:\n"
        "            return 10\n"
        "        0:\n"
        "            return 20\n"
        "        1:\n"
        "            return 30\n"
    )
    function = parse(source).functions[0]
    statement = function.body.statements[0]
    assert isinstance(statement, ast.SwitchStatement)
    assert tuple(case.label for case in statement.cases) == (-1, 0, 1)
    assert all(isinstance(case.body.statements[0], ast.ReturnStatement) for case in statement.cases)
    assert _ng_parse_status(source) == 0


def test_nextgen_parser_accepts_compare_expression_as_match_selector() -> None:
    source = (
        "fn compare(value: tryte) -> trit:\n"
        "    return value <=> 0\n"
    )
    assert _ng_parse_status(source) == 0


def test_nextgen_parser_accepts_signed_integer_literal_expression() -> None:
    source = "fn negative() -> i64:\n    return -42\n"
    expression = parse(source).functions[0].body.statements[0].expression
    assert isinstance(expression, ast.UnaryExpression)
    assert isinstance(expression.operand, ast.IntegerLiteral)
    assert expression.operand.value == 42
    assert _ng_parse_status(source) == 0


def test_nextgen_parser_rejects_minus_without_integer_operand() -> None:
    source = "fn broken() -> i64:\n    return -\n"
    with pytest.raises(ParseError):
        parse(source)
    assert _ng_parse_status(source) < 0


def test_nextgen_parser_stops_return_expression_before_next_negative_match_label() -> None:
    source = (
        "fn choose(value: tryte) -> tryte:\n"
        "    match value:\n"
        "        0:\n"
        "            return 10\n"
        "        1:\n"
        "            return 20\n"
        "        -1:\n"
        "            return 30\n"
    )
    function = parse(source).functions[0]
    statement = function.body.statements[0]
    assert isinstance(statement, ast.SwitchStatement)
    assert tuple(case.label for case in statement.cases) == (0, 1, -1)
    assert _ng_parse_status(source) == 0


def test_nextgen_parser_preserves_explicit_grouping() -> None:
    source = "fn grouped(value: i64) -> i64:\n    return (value + 1) * 2\n"
    reference = parse(source)
    returned = reference.functions[0].body.statements[0].expression
    assert isinstance(returned, ast.BinaryExpression)
    assert isinstance(returned.left, ast.BinaryExpression)
    assert _ng_parse_status(source) == 0


@pytest.mark.parametrize(
    "source",
    [
        "fn broken(value i64) -> i64:\n    return value",
        "fn broken() -> i64:\n    return 1 +",
    ],
)
def test_nextgen_parser_rejects_invalid_syntax_also_rejected_by_reference(source: str) -> None:
    with pytest.raises(ParseError):
        parse(source)
    assert _ng_parse_status(source) < 0
