from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import ParseError, SemanticError
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze


def analyze_source(source: str) -> ast.Program:
    program = parse(source)
    analyze(program)
    return program


def test_parser_supports_zero_one_and_multiple_parameters() -> None:
    program = parse(
        """\
fn zero() -> tryte { return 0; }
fn one(value: tryte) -> tryte { return value; }
fn two(left: tryte, right: trit) -> tryte { return left; }
fn main() -> tryte { return zero(); }
"""
    )
    assert [len(function.parameters) for function in program.functions] == [0, 1, 2, 0]
    assert program.functions[2].parameters[1].type_name is ast.TypeName.TRIT


def test_parser_builds_nested_and_recursive_calls() -> None:
    program = parse(
        """\
fn recurse(value: tryte) -> tryte { return recurse(value); }
fn pair(a: tryte, b: tryte) -> tryte { return a + b; }
fn main() -> tryte { return pair(recurse(1), pair(2, 3)); }
"""
    )
    return_statement = program.functions[-1].body.statements[0]
    assert isinstance(return_statement, ast.ReturnStatement)
    call = return_statement.expression
    assert isinstance(call, ast.CallExpression)
    assert call.function_name == "pair"
    assert len(call.arguments) == 2
    assert isinstance(call.arguments[0], ast.CallArgument)
    assert isinstance(call.arguments[0].expression, ast.CallExpression)


def test_parser_builds_switch_cases_in_any_order() -> None:
    program = parse(
        """\
fn main() -> trit {
    switch (0) {
        1: { return 1; }
        -1: { return -1; }
        0: { return 0; }
    }
}
"""
    )
    statement = program.functions[0].body.statements[0]
    assert isinstance(statement, ast.SwitchStatement)
    assert [case.label for case in statement.cases] == [1, -1, 0]
    assert all(isinstance(case.body, ast.Block) for case in statement.cases)


@pytest.mark.parametrize(
    "source",
    (
        "fn bad(value tryte) -> tryte { return value; }",
        "fn bad(value: tryte,) -> tryte { return value; }",
    ),
)
def test_parameter_syntax_errors(source: str) -> None:
    with pytest.raises(ParseError):
        parse(source)


def test_argument_syntax_error() -> None:
    with pytest.raises(ParseError, match="expected argument"):
        parse("fn main() -> tryte { return missing(1,); }")


def test_case_syntax_error() -> None:
    with pytest.raises(ParseError, match="expected integer case label"):
        parse("fn main() -> trit { switch (0) { value: {} } }")


def test_forward_call_and_direct_recursion_are_resolved() -> None:
    analyze_source(
        """\
fn main() -> tryte { return calculate(3); }
fn calculate(value: tryte) -> tryte {
    switch (value <=> 0) {
        -1: { return 0; }
        0: { return 0; }
        1: { return calculate(value - 1); }
    }
}
"""
    )


def test_unknown_function_is_rejected() -> None:
    with pytest.raises(SemanticError, match="unknown function 'missing'"):
        analyze_source("fn main() -> tryte { return missing(); }")


def test_duplicate_function_is_rejected() -> None:
    with pytest.raises(SemanticError, match="duplicate function 'main'"):
        analyze_source(
            """\
fn main() -> tryte { return 0; }
fn main() -> tryte { return 1; }
"""
        )


def test_duplicate_parameter_is_rejected() -> None:
    with pytest.raises(SemanticError, match="duplicate parameter 'value'"):
        analyze_source(
            """\
fn duplicate(value: tryte, value: tryte) -> tryte { return value; }
fn main() -> tryte { return 0; }
"""
        )


def test_local_cannot_duplicate_parameter_in_function_scope() -> None:
    with pytest.raises(SemanticError, match="conflicts with parameter"):
        analyze_source(
            """\
fn duplicate(value: tryte) -> tryte {
    tryte value = 1;
    return value;
}
fn main() -> tryte { return duplicate(0); }
"""
        )


@pytest.mark.parametrize(
    ("arguments", "actual"),
    (("", 0), ("1, 2", 2)),
)
def test_wrong_argument_count_is_rejected(arguments: str, actual: int) -> None:
    with pytest.raises(
        SemanticError,
        match=rf"expects 1 argument\(s\), got {actual}",
    ):
        analyze_source(
            f"""\
fn identity(value: tryte) -> tryte {{ return value; }}
fn main() -> tryte {{ return identity({arguments}); }}
"""
        )


def test_wrong_argument_type_is_rejected() -> None:
    with pytest.raises(SemanticError, match="has type tryte; expected trit"):
        analyze_source(
            """\
fn accept(value: trit) -> trit { return value; }
fn main() -> trit {
    tryte wrong = 0;
    return accept(wrong);
}
"""
        )


def test_function_cannot_be_used_as_variable() -> None:
    with pytest.raises(SemanticError, match="cannot be used as a variable"):
        analyze_source(
            """\
fn helper() -> tryte { return 0; }
fn main() -> tryte { return helper; }
"""
        )


def test_variable_cannot_be_called() -> None:
    with pytest.raises(SemanticError, match="variable 'value' cannot be called"):
        analyze_source(
            """\
fn main() -> tryte {
    tryte value = 0;
    return value();
}
"""
        )


def test_switch_requires_trit_selector() -> None:
    with pytest.raises(SemanticError, match="has type tryte; expected trit"):
        analyze_source(
            """\
fn main() -> tryte {
    tryte value = 10;
    switch (value) {
        -1: { return 0; }
        0: { return 0; }
        1: { return 0; }
    }
}
"""
        )


def test_switch_rejects_missing_duplicate_and_invalid_cases() -> None:
    with pytest.raises(SemanticError, match="missing case"):
        analyze_source(
            "fn main() -> trit { switch (0) { -1: {} 0: {} } }"
        )
    with pytest.raises(SemanticError, match="duplicate ternary case 1"):
        analyze_source(
            "fn main() -> trit { switch (0) { -1: {} 0: {} 1: {} 1: {} } }"
        )
    with pytest.raises(SemanticError, match="invalid ternary case 2"):
        analyze_source(
            "fn main() -> trit { switch (0) { -1: {} 0: {} 1: {} 2: {} } }"
        )


def test_exhaustive_switch_can_satisfy_return_analysis() -> None:
    analyze_source(
        """\
fn main() -> trit {
    switch (0) {
        -1: { return -1; }
        0: { return 0; }
        1: { return 1; }
    }
}
"""
    )


def test_switch_path_without_return_is_rejected() -> None:
    with pytest.raises(SemanticError, match="path without returning trit"):
        analyze_source(
            """\
fn main() -> trit {
    switch (0) {
        -1: { return -1; }
        0: { return 0; }
        1: { tryte temporary = 1; }
    }
}
"""
        )


def test_statement_after_terminating_switch_is_unreachable() -> None:
    with pytest.raises(SemanticError, match="unreachable statement"):
        analyze_source(
            """\
fn main() -> trit {
    switch (0) {
        -1: { return -1; }
        0: { return 0; }
        1: { return 1; }
    }
    return 0;
}
"""
        )


def test_case_scope_does_not_escape() -> None:
    with pytest.raises(SemanticError, match="undeclared variable 'inside'"):
        analyze_source(
            """\
fn main() -> tryte {
    switch (0) {
        -1: { tryte inside = 1; }
        0: {}
        1: {}
    }
    return inside;
}
"""
        )

