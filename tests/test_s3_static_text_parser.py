from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import ParseError, parse
import pytest

pytestmark = pytest.mark.s3_fast


def test_parses_immutable_static_string_binding() -> None:
    program = parse(
        'fn main() -> tryte:\n    greeting: string = "hello"\n    return 0\n',
        mode=SyntaxMode.V0_6,
    )

    statement = program.functions[0].body.statements[0]
    assert isinstance(statement, ast.VariableDeclaration)
    assert not statement.mutable
    assert statement.type_name == ast.TypeName.STRING
    assert isinstance(statement.initializer, ast.StringLiteral)
    assert statement.initializer.value == "hello"


def test_parses_mutable_static_string_binding() -> None:
    program = parse(
        'fn main() -> tryte:\n    mut current: string = ""\n    return 0\n',
        mode=SyntaxMode.V0_6,
    )

    statement = program.functions[0].body.statements[0]
    assert isinstance(statement, ast.VariableDeclaration)
    assert statement.mutable
    assert statement.name == "current"
    assert statement.type_name == ast.TypeName.STRING


def test_parses_string_parameters_and_return_type() -> None:
    program = parse(
        'fn choose(left: string, right: string) -> string:\n    return left\n',
        mode=SyntaxMode.V0_6,
    )

    function = program.functions[0]
    assert function.return_type == ast.TypeName.STRING
    assert [parameter.type_name for parameter in function.parameters] == [
        ast.TypeName.STRING,
        ast.TypeName.STRING,
    ]


def test_parses_static_string_literal_escapes_as_front_end_text() -> None:
    program = parse(
        'fn main() -> tryte:\n    value: string = "line\\nnext \\"quoted\\""\n    return 0\n',
        mode=SyntaxMode.V0_6,
    )

    statement = program.functions[0].body.statements[0]
    assert isinstance(statement, ast.VariableDeclaration)
    assert isinstance(statement.initializer, ast.StringLiteral)
    assert statement.initializer.value == 'line\\nnext \\"quoted\\"'


def test_parses_static_string_literal_unicode_text() -> None:
    program = parse(
        'fn main() -> tryte:\n    value: string = "olá"\n    return 0\n',
        mode=SyntaxMode.V0_6,
    )

    statement = program.functions[0].body.statements[0]
    assert isinstance(statement, ast.VariableDeclaration)
    assert isinstance(statement.initializer, ast.StringLiteral)
    assert statement.initializer.value == "olá"


def test_string_is_not_a_declaration_keyword_without_a_name() -> None:
    with pytest.raises(ParseError):
        parse(
            'fn main() -> tryte:\n    string value = "hello"\n    return 0\n',
            mode=SyntaxMode.V0_6,
        )
