from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.emulator import EmulatorError, execute_assembly
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse


ROOT = Path(__file__).parents[1]


def test_normative_recursive_assembly_is_valid_and_returns_ten() -> None:
    source = (ROOT / "examples" / "assembly_recursive_sum.s3asm").read_text(
        encoding="utf-8"
    )
    program = parse_assembly(source)
    for function in program.functions:
        declared = set(function.all_register_types)
        for instruction in function.instructions:
            assert set(instruction.registers) <= declared
    assert "TSUB" not in source
    assert execute_assembly(program) == 10


def test_identifier_call_and_nested_call_remain_distinct() -> None:
    program = parse(
        """\
fn inner(value: tryte) -> tryte { return value; }
fn outer(value: tryte) -> tryte { return value; }
fn main() -> tryte {
    tryte value = 1;
    tryte copied = value;
    return outer(inner(1));
}
""",
        mode=SyntaxMode.V0_5,
    )
    statements = program.functions[-1].body.statements
    declaration = statements[1]
    returned = statements[2]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert isinstance(declaration.initializer, ast.Identifier)
    assert isinstance(returned, ast.ReturnStatement)
    assert isinstance(returned.expression, ast.CallExpression)
    assert isinstance(
        returned.expression.arguments[0].expression,
        ast.CallExpression,
    )


def test_structural_cycle_is_stopped_by_instruction_limit() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
.label entry
    TJMP entry
.label return_path
    TCONST r0, 0
    TRET r0
.end
"""
    program = parse_assembly(source)
    with pytest.raises(EmulatorError, match="instruction limit 8 exceeded"):
        execute_assembly(program, max_instructions=8)


def test_ci_workflow_has_required_matrix_and_commands() -> None:
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8"
    )
    assert "name: Tests" in workflow
    assert "push:" in workflow
    assert "pull_request:" in workflow
    assert "ubuntu-latest" in workflow
    assert '["3.11", "3.12", "3.13"]' in workflow
    assert "actions/checkout@v4" in workflow
    assert "actions/setup-python@v5" in workflow
    assert 'python -m pip install -e ".[dev]"' in workflow
    assert "python -m pytest" in workflow
    assert "native-x86-64:" in workflow
    assert "uname -m" in workflow
    assert "cc --version" in workflow
    assert "as --version" in workflow
    assert "ld --version" in workflow
    assert "file --version" in workflow
    assert "readelf --version" in workflow
    assert 'S3_NATIVE_REQUIRED: "1"' in workflow
    assert "continue-on-error" not in workflow


def test_normative_ebnf_defines_composable_postfix() -> None:
    grammar = (ROOT / "spec" / "grammar.ebnf").read_text(encoding="utf-8")
    assert "unary                = (\"~\" | \"-\"), unary | postfix-expression" in grammar
    assert "postfix-expression   = primary, { postfix-suffix }" in grammar
    assert "postfix-suffix       = call-suffix | index-suffix | member-suffix" in grammar
    assert 'call-suffix          = "(", [ argument-list ], ")"' in grammar
    assert 'index-suffix         = "[", expression, "]"' in grammar
    assert 'member-suffix        = ".", identifier' in grammar
    assert "identifier-expression" not in grammar
    assert "qualified-name" not in grammar
    assert "primary              = integer | identifier | call" not in grammar
