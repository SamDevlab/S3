from __future__ import annotations

import json
import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import ParseError, DiagnosticCode, SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze
from bootstrap.s3.lowering import lower
from bootstrap.s3.verifier import verify_ir
from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.emulator import Emulator

def test_simple_match():
    source = """\
fn main() -> tryte:
    match 0:
        -1:
            return -1
        0:
            return 0
        1:
            return 1
"""
    program = parse(source, mode=SyntaxMode.V0_6)
    match_stmt = program.functions[0].body.statements[0]
    assert isinstance(match_stmt, ast.SwitchStatement)
    assert len(match_stmt.cases) == 3
    assert match_stmt.cases[0].label == -1
    assert match_stmt.cases[1].label == 0
    assert match_stmt.cases[2].label == 1

def test_expression_compare():
    source = """\
fn main() -> tryte:
    match 1 <=> 0:
        -1:
            return -1
        0:
            return 0
        1:
            return 1
"""
    program = parse(source, mode=SyntaxMode.V0_6)
    match_stmt = program.functions[0].body.statements[0]
    assert isinstance(match_stmt.expression, ast.BinaryExpression)
    assert match_stmt.expression.operator == ast.BinaryOperator.COMPARE

def test_statements_in_arms():
    source = """\
fn do_nothing() -> tryte:
    return 0

fn main() -> tryte:
    match 0:
        -1:
            v: tryte = 1
            return v
        0:
            mut c: tryte = 0
            c = 1
            return c
        1:
            return do_nothing()
"""
    program = parse(source, mode=SyntaxMode.V0_6)
    match_stmt = program.functions[1].body.statements[0]
    assert isinstance(match_stmt.cases[0].body.statements[0], ast.VariableDeclaration)
    assert isinstance(match_stmt.cases[1].body.statements[1], ast.AssignmentStatement)
    assert isinstance(match_stmt.cases[2].body.statements[0], ast.ReturnStatement)
    assert isinstance(match_stmt.cases[2].body.statements[0].expression, ast.CallExpression)

def test_nested_match():
    source = """\
fn main() -> tryte:
    match 0:
        -1:
            return -1
        0:
            match 1:
                -1:
                    return -1
                0:
                    return 0
                1:
                    return 1
            return 0
        1:
            return 1
"""
    program = parse(source, mode=SyntaxMode.V0_6)
    match_stmt = program.functions[0].body.statements[0]
    assert isinstance(match_stmt.cases[1].body.statements[0], ast.SwitchStatement)

def test_comments_and_blank_lines_between_arms():
    source = """\
fn main() -> tryte:
    match 0:
        # comment
        -1:
            return -1

        0:
            return 0
        # another comment
        1:
            return 1
"""
    program = parse(source, mode=SyntaxMode.V0_6)
    match_stmt = program.functions[0].body.statements[0]
    assert len(match_stmt.cases) == 3

def test_last_line_without_newline():
    source = "fn main() -> tryte:\n    match 0:\n        -1:\n            return -1\n        0:\n            return 0\n        1:\n            return 1"
    program = parse(source, mode=SyntaxMode.V0_6)
    match_stmt = program.functions[0].body.statements[0]
    assert len(match_stmt.cases) == 3

def test_ast_equivalence_v0_5_and_v0_6():
    source_v0_5 = """\
    fn sign(value: tryte) -> trit {
        switch (value <=> 0) {
            -1: { return -1; }
            0: { return 0; }
            1: { return 1; }
        }
    }
"""
    source_v0_6 = """\
fn sign(value: tryte) -> trit:
    match value <=> 0:
        -1:
            return -1
        0:
            return 0
        1:
            return 1
"""
    ast_v0_5 = ast.to_dict(parse(source_v0_5, mode=SyntaxMode.V0_5))
    ast_v0_6 = ast.to_dict(parse(source_v0_6, mode=SyntaxMode.V0_6))

    # Ignore locations
    def remove_locations(d):
        if isinstance(d, dict):
            return {k: remove_locations(v) for k, v in d.items() if k != "location"}
        if isinstance(d, list):
            return [remove_locations(v) for v in d]
        return d

    assert remove_locations(ast_v0_5) == remove_locations(ast_v0_6)

@pytest.mark.parametrize("val, expected", [(-1, -1), (0, 0), (1, 1)])
def test_internal_pipeline_cases(val: int, expected: int):
    # Tests discriminant from call, nested match, mutable modification, and function calls.
    source = f"""\
fn get_val() -> tryte:
    return {val}

fn sign(value: tryte) -> tryte:
    mut result: tryte = 99
    match value <=> 0:
        -1:
            result = -1
        0:
            match 0:
                -1:
                    result = 99
                0:
                    result = 0
                1:
                    result = 99
        1:
            result = 1
    return result

fn main() -> tryte:
    return sign(get_val())
"""
    program = parse(source, mode=SyntaxMode.V0_6)
    analyzed = analyze(program)
    ir = lower(program, analyzed)
    verify_ir(ir)
    asm = generate_assembly(ir)
    assert Emulator().execute(asm) == expected

def test_missing_colon_on_match():
    source = """\
fn main() -> tryte:
    match 0
        -1:
            return -1
"""
    with pytest.raises(ParseError, match="expected ':'"):
        parse(source, mode=SyntaxMode.V0_6)

def test_missing_colon_on_arm():
    source = """\
fn main() -> tryte:
    match 0:
        -1
            return -1
"""
    with pytest.raises(ParseError, match="expected ':'"):
        parse(source, mode=SyntaxMode.V0_6)

def test_missing_newline():
    source = """\
fn main() -> tryte:
    match 0: return 0
"""
    with pytest.raises(ParseError, match="expected newline"):
        parse(source, mode=SyntaxMode.V0_6)

def test_missing_indent_match():
    source = "fn main() -> tryte:\n    match 0:\n    -1:\n        return -1\n"
    with pytest.raises(ParseError, match="expected indented block"):
        parse(source, mode=SyntaxMode.V0_6)

def test_missing_indent_arm():
    source = "fn main() -> tryte:\n    match 0:\n        -1:\n        return -1\n"
    with pytest.raises(ParseError, match="expected indented block"):
        parse(source, mode=SyntaxMode.V0_6)

def test_empty_arm():
    source = "fn main() -> tryte:\n    match 0:\n        -1:\n        0:\n            return 0\n"
    with pytest.raises(ParseError, match="expected indented block"):
        parse(source, mode=SyntaxMode.V0_6)

def test_arm_only_comment():
    source = "fn main() -> tryte:\n    match 0:\n        -1:\n            # only comment\n        0:\n            return 0\n"
    with pytest.raises(ParseError, match="expected indented block"):
        parse(source, mode=SyntaxMode.V0_6)

def test_invalid_label_2():
    source = "fn main() -> tryte:\n    match 0:\n        2:\n            return 0\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    with pytest.raises(SemanticError, match="invalid ternary case"):
        analyze(program)

def test_invalid_label_minus_2():
    source = "fn main() -> tryte:\n    match 0:\n        -2:\n            return 0\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    with pytest.raises(SemanticError, match="invalid ternary case"):
        analyze(program)

def test_label_by_expression():
    source = "fn main() -> tryte:\n    match 0:\n        1 + 1:\n            return 0\n"
    with pytest.raises(ParseError, match="expected ':' after case label"):
        parse(source, mode=SyntaxMode.V0_6)

def test_duplicate_arm():
    source = "fn main() -> tryte:\n    match 0:\n        -1:\n            return -1\n        -1:\n            return -1\n        0:\n            return 0\n        1:\n            return 1\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    with pytest.raises(SemanticError, match="duplicate ternary case"):
        analyze(program)

def test_missing_arm():
    source = "fn main() -> tryte:\n    match 0:\n        -1:\n            return -1\n        1:\n            return 1\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    with pytest.raises(SemanticError, match="ternary switch is missing case"):
        analyze(program)

def test_extra_arm():
    source = "fn main() -> tryte:\n    match 0:\n        -1:\n            return -1\n        0:\n            return 0\n        1:\n            return 1\n        2:\n            return 2\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    with pytest.raises(SemanticError, match="invalid ternary case"):
        analyze(program)

def test_alternative_order():
    source = "fn main() -> tryte:\n    match 0:\n        1:\n            return 1\n        0:\n            return 0\n        -1:\n            return -1\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    analyze(program)

def test_use_case_keyword():
    source = "fn main() -> tryte:\n    match 0:\n        case -1:\n            return -1\n"
    with pytest.raises(ParseError, match="expected integer case label"):
        parse(source, mode=SyntaxMode.V0_6)

def test_use_else_keyword():
    source = "fn main() -> tryte:\n    match 0:\n        else:\n            return -1\n"
    with pytest.raises(ParseError, match="expected integer case label"):
        parse(source, mode=SyntaxMode.V0_6)

def test_use_underscore():
    source = "fn main() -> tryte:\n    match 0:\n        _:\n            return -1\n"
    with pytest.raises(ParseError, match="expected integer case label"):
        parse(source, mode=SyntaxMode.V0_6)

def test_obsolete_switch_in_v0_6():
    source = "fn main() -> tryte:\n    switch 0:\n        -1:\n            return -1\n"
    with pytest.raises(ParseError) as exc_info:
        parse(source, mode=SyntaxMode.V0_6)
    assert exc_info.value.diagnostic_code == DiagnosticCode.PARSE_OBSOLETE_SWITCH

def test_switch_valid_in_v0_5():
    source = "fn sign() -> trit { switch (0) { -1: { return -1; } 0: { return 0; } 1: { return 1; } } }"
    program = parse(source, mode=SyntaxMode.V0_5)
    assert len(program.functions[0].body.statements) == 1

def test_match_is_identifier_in_v0_5():
    source = "fn main() -> tryte { mut tryte match = 0; return match; }"
    program = parse(source, mode=SyntaxMode.V0_5)
    assert len(program.functions[0].body.statements) == 2

def test_diagnostic_json():
    source = "fn main() -> tryte:\n    switch 0:\n        -1:\n            return -1\n"
    with pytest.raises(ParseError) as exc_info:
        parse(source, mode=SyntaxMode.V0_6)

    from bootstrap.s3.diagnostics import diagnostic_from_exception
    diagnostic = diagnostic_from_exception(exc_info.value)
    data = json.loads(diagnostic.to_json())
    assert data["code"] == "S3E_PARSE_OBSOLETE_SWITCH"
    assert data["category"] == "syntax"

def test_diagnostic_text():
    source = "fn main() -> tryte:\n    switch 0:\n        -1:\n            return -1\n"
    with pytest.raises(ParseError, match="obsolete 'switch' syntax, use 'match'"):
        parse(source, mode=SyntaxMode.V0_6)

def test_default_mode_is_v0_5():
    source = "fn sign() -> trit { switch (0) { -1: { return -1; } 0: { return 0; } 1: { return 1; } } }"
    program = parse(source)
    assert len(program.functions[0].body.statements) == 1
