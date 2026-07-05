from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import ParseError, SemanticError
from bootstrap.s3.lexer import SyntaxMode, TokenKind, tokenize
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze


def analyze_source(source: str) -> ast.Program:
    program = parse(source, mode=SyntaxMode.V0_5)
    analyze(program)
    return program


def test_lexer_recognizes_mut_brackets_and_separate_negative_sign() -> None:
    tokens = tokenize(
        "fn main() -> trit { mut trit[3] states = [-1, 0, 1]; return states[2]; }",
        mode=SyntaxMode.V0_5,
    )
    kinds = [token.kind for token in tokens]
    assert TokenKind.MUT in kinds
    assert kinds.count(TokenKind.LEFT_BRACKET) == 3
    assert kinds.count(TokenKind.RIGHT_BRACKET) == 3
    minus = tokens[kinds.index(TokenKind.MINUS)]
    assert minus.text == "-"
    assert tokens[tokens.index(minus) + 1].kind is TokenKind.INTEGER


def test_parser_builds_mutable_assignment_and_array_nodes() -> None:
    program = parse(
        """\
fn main() -> tryte {
    mut tryte value = 10;
    value = value + 1;
    mut tryte[2] values = [1, 2];
    values[1] = value;
    return values[0];
}
""",
        mode=SyntaxMode.V0_5,
    )
    statements = program.functions[0].body.statements
    scalar = statements[0]
    assignment = statements[1]
    array = statements[2]
    element_assignment = statements[3]
    returned = statements[4]
    assert isinstance(scalar, ast.VariableDeclaration) and scalar.mutable
    assert isinstance(assignment, ast.AssignmentStatement)
    assert isinstance(assignment.target, ast.VariableTarget)
    assert isinstance(array, ast.VariableDeclaration) and array.mutable
    assert isinstance(array.type_name, ast.ArrayType)
    assert array.type_name.length == 2
    assert isinstance(array.initializer, ast.ArrayLiteral)
    assert isinstance(element_assignment, ast.AssignmentStatement)
    assert isinstance(element_assignment.target, ast.IndexTarget)
    assert isinstance(returned, ast.ReturnStatement)
    assert isinstance(returned.expression, ast.IndexExpression)


def test_call_and_indexing_are_both_postfix_primaries() -> None:
    program = parse(
        """\
fn identity(value: tryte) -> tryte { return value; }
fn main() -> tryte {
    tryte[1] values = [identity(1)];
    return values[0] + identity(2);
}
""",
        mode=SyntaxMode.V0_5,
    )
    declaration = program.functions[1].body.statements[0]
    returned = program.functions[1].body.statements[1]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert isinstance(declaration.initializer, ast.ArrayLiteral)
    assert isinstance(declaration.initializer.elements[0], ast.CallExpression)
    assert isinstance(returned, ast.ReturnStatement)
    assert isinstance(returned.expression, ast.BinaryExpression)
    assert isinstance(returned.expression.left, ast.IndexExpression)
    assert isinstance(returned.expression.right, ast.CallExpression)


@pytest.mark.parametrize(
    "source",
    (
        "fn main() -> tryte { tryte[2 values = [1, 2]; return 0; }",
        "fn main() -> tryte { tryte[2] values = [1, 2; return 0; }",
        "fn main() -> tryte { tryte[2] values = [1, 2,]; return 0; }",
        "fn main() -> tryte { tryte[2] values = [1, 2]; return values[0; }",
    ),
)
def test_array_bracket_and_literal_syntax_errors(source: str) -> None:
    with pytest.raises(ParseError):
        parse(source, mode=SyntaxMode.V0_5)


def test_valid_scalar_assignment_is_semantically_accepted() -> None:
    analyze_source(
        """\
fn main() -> tryte {
    mut tryte value = 10;
    value = value + 5;
    return value;
}
"""
    )


def test_assignment_to_immutable_is_rejected() -> None:
    with pytest.raises(SemanticError, match="immutable variable"):
        analyze_source(
            "fn main() -> tryte { tryte value = 10; value = 20; return value; }"
        )


def test_assignment_to_parameter_is_rejected() -> None:
    with pytest.raises(SemanticError, match="assign to a parameter"):
        analyze_source(
            """\
fn alter(value: tryte) -> tryte { value = 1; return value; }
fn main() -> tryte { return alter(0); }
"""
        )


def test_assignment_to_unknown_name_and_function_are_rejected() -> None:
    with pytest.raises(SemanticError, match="undeclared variable 'missing'"):
        analyze_source("fn main() -> tryte { missing = 1; return 0; }")
    with pytest.raises(SemanticError, match="cannot be an assignment target"):
        analyze_source(
            """\
fn helper() -> tryte { return 0; }
fn main() -> tryte { helper = 1; return 0; }
"""
        )


def test_assignment_type_mismatch_is_rejected() -> None:
    with pytest.raises(SemanticError, match="has type tryte; expected trit"):
        analyze_source(
            """\
fn main() -> trit {
    mut trit result = 0;
    tryte wrong = 1;
    result = wrong;
    return result;
}
"""
        )


def test_mutable_can_be_written_in_cases_and_read_after_switch() -> None:
    analyze_source(
        """\
fn classify(value: tryte) -> tryte {
    mut tryte result = 0;
    switch (value <=> 0) {
        -1: { result = -10; }
        0: { result = 0; }
        1: { result = 10; }
    }
    return result;
}
fn main() -> tryte { return classify(5); }
"""
    )


def test_valid_static_array_and_element_assignment() -> None:
    analyze_source(
        """\
fn main() -> tryte {
    mut tryte[4] values = [1, 2, 3, 4];
    values[1] = 5;
    return values[0] + values[1];
}
"""
    )


@pytest.mark.parametrize("length", ("0", "-1"))
def test_nonpositive_array_length_is_rejected(length: str) -> None:
    with pytest.raises(SemanticError, match="array length must be positive"):
        analyze_source(
            f"fn main() -> tryte {{ tryte[{length}] values = []; return 0; }}"
        )


def test_array_length_cannot_exceed_tryte_index_space() -> None:
    with pytest.raises(SemanticError, match="exceeds tryte-indexed maximum 365"):
        analyze_source(
            "fn main() -> tryte { tryte[366] values = []; return 0; }"
        )


@pytest.mark.parametrize(
    ("literal", "count"),
    (("[1]", 1), ("[1, 2, 3]", 3)),
)
def test_array_initializer_length_must_match(literal: str, count: int) -> None:
    with pytest.raises(
        SemanticError,
        match=rf"initializer has {count} element",
    ):
        analyze_source(
            f"fn main() -> tryte {{ tryte[2] values = {literal}; return 0; }}"
        )


def test_array_element_type_is_checked() -> None:
    with pytest.raises(SemanticError, match=r"outside trit range"):
        analyze_source(
            "fn main() -> trit { trit[1] states = [2]; return states[0]; }"
        )


def test_index_must_be_tryte() -> None:
    with pytest.raises(SemanticError, match="has type trit; expected tryte"):
        analyze_source(
            """\
fn main() -> tryte {
    tryte[2] values = [1, 2];
    trit index = 1;
    return values[index];
}
"""
        )


@pytest.mark.parametrize("index", ("-1", "2", "1 + 1"))
def test_constant_out_of_bounds_index_is_rejected(index: str) -> None:
    with pytest.raises(SemanticError, match="outside array 'values' bounds"):
        analyze_source(
            f"""\
fn main() -> tryte {{
    tryte[2] values = [1, 2];
    return values[{index}];
}}
"""
        )


def test_immutable_array_cannot_be_modified() -> None:
    with pytest.raises(SemanticError, match="immutable variable"):
        analyze_source(
            """\
fn main() -> tryte {
    tryte[2] values = [1, 2];
    values[0] = 3;
    return values[0];
}
"""
        )


def test_arrays_cannot_be_returned_passed_or_used_by_operators() -> None:
    with pytest.raises(SemanticError, match="arrays cannot be returned"):
        analyze_source(
            "fn main() -> tryte { tryte[1] values = [1]; return values; }"
        )
    with pytest.raises(SemanticError, match="arrays cannot be passed"):
        analyze_source(
            """\
fn accept(value: tryte) -> tryte { return value; }
fn main() -> tryte { tryte[1] values = [1]; return accept(values); }
"""
        )
    with pytest.raises(SemanticError, match="cannot be used as a scalar"):
        analyze_source(
            "fn main() -> tryte { tryte[1] values = [1]; return values + 1; }"
        )


def test_array_signatures_nested_arrays_and_whole_assignment_are_rejected() -> None:
    with pytest.raises(SemanticError, match="function parameters"):
        analyze_source(
            """\
fn bad(values: tryte[1]) -> tryte { return 0; }
fn main() -> tryte { return 0; }
"""
        )
    with pytest.raises(SemanticError, match="nested arrays"):
        analyze_source(
            "fn main() -> tryte { tryte[2][2] values = []; return 0; }"
        )
    with pytest.raises(SemanticError, match="whole-array assignment"):
        analyze_source(
            """\
fn main() -> tryte {
    mut tryte[1] values = [1];
    values = [2];
    return values[0];
}
"""
        )
