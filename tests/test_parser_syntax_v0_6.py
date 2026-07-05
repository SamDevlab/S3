from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse, ParseError
from bootstrap.s3.diagnostics import DiagnosticCode
import pytest

def test_simple_function():
    source = "fn main() -> tryte:\n    return 6\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    assert len(program.functions) == 1
    func = program.functions[0]
    assert func.name == "main"
    assert func.return_type == ast.TypeName.TRYTE
    assert len(func.body.statements) == 1
    assert isinstance(func.body.statements[0], ast.ReturnStatement)
    assert isinstance(func.body.statements[0].expression, ast.IntegerLiteral)

def test_function_with_parameters():
    source = "fn add(a: tryte, b: tryte) -> tryte:\n    return a + b\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    func = program.functions[0]
    assert len(func.parameters) == 2
    assert func.parameters[0].name == "a"
    assert func.parameters[1].name == "b"

def test_multiple_functions():
    source = "fn a() -> tryte:\n    return 1\nfn b() -> tryte:\n    return 2\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    assert len(program.functions) == 2

def test_immutable_declaration():
    source = "fn main() -> tryte:\n    value: tryte = 5\n    return value\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, ast.VariableDeclaration)
    assert not stmt.mutable
    assert stmt.name == "value"
    assert stmt.type_name == ast.TypeName.TRYTE

def test_mutable_declaration():
    source = "fn main() -> tryte:\n    mut counter: tryte = 0\n    return counter\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, ast.VariableDeclaration)
    assert stmt.mutable
    assert stmt.name == "counter"

def test_assignment():
    source = "fn main() -> tryte:\n    mut counter: tryte = 0\n    counter = counter + 1\n    return counter\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    stmt = program.functions[0].body.statements[1]
    assert isinstance(stmt, ast.AssignmentStatement)
    assert isinstance(stmt.target, ast.VariableTarget)
    assert stmt.target.name == "counter"

def test_multiline_expression():
    source = "fn main() -> tryte:\n    value: tryte = add(\n        1,\n        2\n    )\n    return value\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, ast.VariableDeclaration)

def test_missing_colon():
    source = "fn main() -> tryte\n    return 0\n"
    with pytest.raises(ParseError) as exc:
        parse(source, mode=SyntaxMode.V0_6)
    assert "expected ':' after return type" in str(exc.value)

def test_missing_newline_after_colon():
    source = "fn main() -> tryte: return 0\n"
    with pytest.raises(ParseError) as exc:
        parse(source, mode=SyntaxMode.V0_6)
    assert "expected newline after ':'" in str(exc.value)

def test_missing_indent():
    source = "fn main() -> tryte:\nreturn 0\n"
    with pytest.raises(ParseError) as exc:
        parse(source, mode=SyntaxMode.V0_6)
    assert "expected indented block" in str(exc.value)

def test_empty_body():
    source = "fn main() -> tryte:\n\nfn b() -> trit:\n    return 0\n"
    with pytest.raises(ParseError) as exc:
        parse(source, mode=SyntaxMode.V0_6)
    assert "expected indented block" in str(exc.value)

def test_obsolete_brace():
    source = "fn main() -> tryte {\n    return 0\n}\n"
    with pytest.raises(ParseError) as exc:
        parse(source, mode=SyntaxMode.V0_6)
    assert exc.value.diagnostic_code == DiagnosticCode.PARSE_OBSOLETE_BRACE

def test_obsolete_semicolon():
    source = "fn main() -> tryte:\n    return 0;\n"
    with pytest.raises(ParseError) as exc:
        parse(source, mode=SyntaxMode.V0_6)
    assert exc.value.diagnostic_code == DiagnosticCode.PARSE_OBSOLETE_SEMICOLON

def test_invalid_declaration():
    # 'mut value = 1' missing type
    source = "fn main() -> tryte:\n    mut value = 1\n    return 0\n"
    with pytest.raises(ParseError):
        parse(source, mode=SyntaxMode.V0_6)

def test_ast_equivalence():
    source_v0_5 = "fn add(a: tryte, b: tryte) -> tryte {\n    mut tryte c = a + b;\n    c = c + 1;\n    return c;\n}\n"
    source_v0_6 = "fn add(a: tryte, b: tryte) -> tryte:\n    mut c: tryte = a + b\n    c = c + 1\n    return c\n"
    
    ast_v0_5 = ast.to_dict(parse(source_v0_5, mode=SyntaxMode.V0_5))
    ast_v0_6 = ast.to_dict(parse(source_v0_6, mode=SyntaxMode.V0_6))
    
    # Strip location fields for equivalence comparison
    def strip_locations(node):
        if isinstance(node, dict):
            return {k: strip_locations(v) for k, v in node.items() if k != 'location'}
        if isinstance(node, list):
            return [strip_locations(v) for v in node]
        return node

    assert strip_locations(ast_v0_5) == strip_locations(ast_v0_6)

def test_v0_6_default():
    source = "fn main() -> tryte:\n    a: tryte = 1\n    return a\n"
    program1 = parse(source)
    program2 = parse(source, mode=SyntaxMode.V0_6)
    assert ast.to_dict(program1) == ast.to_dict(program2)

def test_comments_ignored_v0_6():
    source = "fn main() -> tryte:\n    # start\n    mut a: tryte = 1\n    # mid\n    a = 2\n    return a # end\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    assert len(program.functions[0].body.statements) == 3

def test_content_on_same_line_after_colon():
    source = "fn main() -> tryte: return 0\n"
    with pytest.raises(ParseError, match="expected newline after ':'"):
        parse(source, mode=SyntaxMode.V0_6)

def test_unexpected_indent_at_top():
    source = "    fn main() -> tryte:\n        return 0\n"
    with pytest.raises(ParseError):
        parse(source, mode=SyntaxMode.V0_6)

def test_body_only_with_comment():
    source = "fn main() -> tryte:\n    # comment only\n"
    with pytest.raises(ParseError, match="expected indented block"):
        parse(source, mode=SyntaxMode.V0_6)

def test_token_between_functions():
    source = "fn a() -> tryte:\n    return 0\nbad_token\nfn b() -> tryte:\n    return 0\n"
    with pytest.raises(ParseError):
        parse(source, mode=SyntaxMode.V0_6)

def test_invalid_declaration_forms():
    # value: tryte (missing initializer)
    with pytest.raises(ParseError):
        parse("fn main() -> tryte:\n    value: tryte\n    return 0\n", mode=SyntaxMode.V0_6)
    # value: = 5 (missing type)
    with pytest.raises(ParseError):
        parse("fn main() -> tryte:\n    value: = 5\n    return 0\n", mode=SyntaxMode.V0_6)
    # value tryte = 5
    with pytest.raises(ParseError):
        parse("fn main() -> tryte:\n    value tryte = 5\n    return 0\n", mode=SyntaxMode.V0_6)
    # let value: tryte = 5
    with pytest.raises(ParseError):
        parse("fn main() -> tryte:\n    let value: tryte = 5\n    return 0\n", mode=SyntaxMode.V0_6)
    # var value: tryte = 5
    with pytest.raises(ParseError):
        parse("fn main() -> tryte:\n    var value: tryte = 5\n    return 0\n", mode=SyntaxMode.V0_6)
    # value := 5
    with pytest.raises(ParseError):
        parse("fn main() -> tryte:\n    value := 5\n    return 0\n", mode=SyntaxMode.V0_6)

def test_value_equals_is_assignment():
    source = "fn main() -> tryte:\n    value = 5\n    return 0\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    stmt = program.functions[0].body.statements[0]
    assert isinstance(stmt, ast.AssignmentStatement)

def test_return_without_expression():
    with pytest.raises(ParseError):
        parse("fn main() -> tryte:\n    return\n", mode=SyntaxMode.V0_6)

def test_return_multiline():
    source = "fn main() -> tryte:\n    return add(\n        1,\n        2\n    )\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    assert isinstance(program.functions[0].body.statements[0], ast.ReturnStatement)

def test_return_extra_token():
    with pytest.raises(ParseError):
        parse("fn main() -> tryte:\n    return 1 2\n", mode=SyntaxMode.V0_6)

def test_return_eof_without_newline():
    source = "fn main() -> tryte:\n    return 1"
    program = parse(source, mode=SyntaxMode.V0_6)
    assert isinstance(program.functions[0].body.statements[0], ast.ReturnStatement)

def test_internal_pipeline_v0_6():
    from bootstrap.s3.semantic import analyze
    from bootstrap.s3.lowering import lower
    source = "fn main() -> tryte:\n    mut a: tryte = 10\n    a = a + 5\n    return a\n"
    program = parse(source, mode=SyntaxMode.V0_6)
    analyzed = analyze(program)
    ir = lower(program, analyzed)
    assert len(ir.functions) == 1
