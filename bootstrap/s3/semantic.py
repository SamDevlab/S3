"""Two-phase name, type, scope, and return-path analysis for S3."""

from __future__ import annotations

from dataclasses import dataclass

from . import ast
from .diagnostics import SemanticError, SourceLocation
from .ternary import TRIT_MAX, TRIT_MIN, TRYTE_MAX, TRYTE_MIN


@dataclass(frozen=True, slots=True)
class FunctionType:
    name: str
    parameter_types: tuple[ast.TypeName, ...]
    return_type: ast.TypeName
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class SemanticModel:
    """Expression types and the complete file-level function table."""

    expression_types: dict[int, ast.TypeName]
    functions: dict[str, FunctionType]

    def type_of(self, expression: ast.Expression) -> ast.TypeName:
        try:
            return self.expression_types[id(expression)]
        except KeyError as error:
            raise SemanticError(
                "internal error: expression has no semantic type",
                expression.location,
            ) from error

    def function(self, name: str) -> FunctionType:
        try:
            return self.functions[name]
        except KeyError as error:
            raise SemanticError(f"unknown function '{name}'") from error


class SemanticAnalyzer:
    def __init__(self) -> None:
        self.expression_types: dict[int, ast.TypeName] = {}
        self.functions: dict[str, FunctionType] = {}
        self.scopes: list[dict[str, ast.TypeName]] = []
        self.parameter_names: set[str] = set()
        self.return_type = ast.TypeName.TRYTE

    def analyze(self, program: ast.Program) -> SemanticModel:
        self._collect_signatures(program)
        if "main" not in self.functions:
            raise SemanticError("program must declare a 'main' function", program.location)
        main = self.functions["main"]
        if main.parameter_types:
            raise SemanticError(
                "entry function 'main' must not declare parameters",
                main.location,
            )
        for function in program.functions:
            self._analyze_function(function)
        return SemanticModel(dict(self.expression_types), dict(self.functions))

    def _collect_signatures(self, program: ast.Program) -> None:
        for function in program.functions:
            if function.name in self.functions:
                raise SemanticError(
                    f"duplicate function '{function.name}'",
                    function.location,
                )
            parameter_names: set[str] = set()
            for parameter in function.parameters:
                if parameter.name in parameter_names:
                    raise SemanticError(
                        f"duplicate parameter '{parameter.name}'",
                        parameter.location,
                    )
                parameter_names.add(parameter.name)
            self.functions[function.name] = FunctionType(
                function.name,
                tuple(parameter.type_name for parameter in function.parameters),
                function.return_type,
                function.signature.location,
            )

    def _analyze_function(self, function: ast.FunctionDeclaration) -> None:
        self.return_type = function.return_type
        self.parameter_names = {parameter.name for parameter in function.parameters}
        self.scopes = [
            {parameter.name: parameter.type_name for parameter in function.parameters}
        ]
        definitely_returns = self._analyze_block(function.body, create_scope=False)
        if not definitely_returns:
            raise SemanticError(
                f"function '{function.name}' has a path without returning "
                f"{function.return_type.value}",
                function.location,
            )

    def _analyze_block(self, block: ast.Block, *, create_scope: bool) -> bool:
        if create_scope:
            self.scopes.append({})
        definitely_returns = False
        try:
            for statement in block.statements:
                if definitely_returns:
                    raise SemanticError(
                        "unreachable statement after return or terminating switch",
                        statement.location,
                    )
                definitely_returns = self._analyze_statement(statement)
            return definitely_returns
        finally:
            if create_scope:
                self.scopes.pop()

    def _analyze_statement(self, statement: ast.Statement) -> bool:
        if isinstance(statement, ast.VariableDeclaration):
            self._analyze_declaration(statement)
            return False
        if isinstance(statement, ast.ReturnStatement):
            actual = self._analyze_expression(statement.expression, self.return_type)
            self._require_type(
                actual,
                self.return_type,
                statement.expression.location,
                "returned expression",
            )
            return True
        if isinstance(statement, ast.SwitchStatement):
            return self._analyze_switch(statement)
        raise SemanticError("unsupported statement", statement.location)

    def _analyze_switch(self, statement: ast.SwitchStatement) -> bool:
        selector_type = self._analyze_expression(
            statement.expression,
            ast.TypeName.TRIT,
        )
        self._require_type(
            selector_type,
            ast.TypeName.TRIT,
            statement.expression.location,
            "switch expression",
        )
        cases: dict[int, ast.TernaryCase] = {}
        for case in statement.cases:
            if case.label not in {-1, 0, 1}:
                raise SemanticError(
                    f"invalid ternary case {case.label}; expected -1, 0, or 1",
                    case.location,
                )
            if case.label in cases:
                raise SemanticError(
                    f"duplicate ternary case {case.label}",
                    case.location,
                )
            cases[case.label] = case
        missing = sorted({-1, 0, 1} - cases.keys())
        if missing:
            rendered = ", ".join(str(label) for label in missing)
            raise SemanticError(
                f"ternary switch is missing case(s): {rendered}",
                statement.location,
            )
        returns = [
            self._analyze_block(cases[label].body, create_scope=True)
            for label in (-1, 0, 1)
        ]
        return all(returns)

    def _analyze_declaration(self, declaration: ast.VariableDeclaration) -> None:
        current_scope = self.scopes[-1]
        if declaration.name in current_scope:
            if declaration.name in self.parameter_names and len(self.scopes) == 1:
                raise SemanticError(
                    f"local variable '{declaration.name}' conflicts with parameter "
                    f"'{declaration.name}'",
                    declaration.location,
                )
            raise SemanticError(
                f"duplicate declaration of variable '{declaration.name}'",
                declaration.location,
            )
        initializer_type = self._analyze_expression(
            declaration.initializer,
            declaration.type_name,
        )
        self._require_type(
            initializer_type,
            declaration.type_name,
            declaration.initializer.location,
            f"initializer for '{declaration.name}'",
        )
        current_scope[declaration.name] = declaration.type_name

    def _analyze_expression(
        self,
        expression: ast.Expression,
        expected: ast.TypeName | None = None,
    ) -> ast.TypeName:
        if isinstance(expression, ast.IntegerLiteral):
            result = expected or ast.TypeName.TRYTE
            self._validate_literal(expression, result)
        elif isinstance(expression, ast.Identifier):
            result = self._identifier_type(expression)
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    f"variable '{expression.name}'",
                )
        elif isinstance(expression, ast.CallExpression):
            result = self._analyze_call(expression)
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    f"call to '{expression.function_name}'",
                )
        elif isinstance(expression, ast.UnaryExpression):
            result = self._analyze_expression(expression.operand, expected)
        elif isinstance(expression, ast.BinaryExpression):
            result = self._analyze_binary(expression, expected)
        else:
            raise SemanticError("unsupported expression", expression.location)
        self.expression_types[id(expression)] = result
        return result

    def _analyze_call(self, expression: ast.CallExpression) -> ast.TypeName:
        if self._lookup_variable(expression.function_name) is not None:
            raise SemanticError(
                f"variable '{expression.function_name}' cannot be called",
                expression.location,
            )
        signature = self.functions.get(expression.function_name)
        if signature is None:
            raise SemanticError(
                f"unknown function '{expression.function_name}'",
                expression.location,
            )
        if len(expression.arguments) != len(signature.parameter_types):
            raise SemanticError(
                f"function '{expression.function_name}' expects "
                f"{len(signature.parameter_types)} argument(s), got "
                f"{len(expression.arguments)}",
                expression.location,
            )
        for index, (argument, parameter_type) in enumerate(
            zip(
                expression.arguments,
                signature.parameter_types,
                strict=True,
            ),
            start=1,
        ):
            actual = self._analyze_expression(argument.expression, parameter_type)
            self._require_type(
                actual,
                parameter_type,
                argument.location,
                f"argument {index} to '{expression.function_name}'",
            )
        return signature.return_type

    def _analyze_binary(
        self,
        expression: ast.BinaryExpression,
        expected: ast.TypeName | None,
    ) -> ast.TypeName:
        if expression.operator is ast.BinaryOperator.COMPARE:
            if expected is not None:
                self._require_type(
                    ast.TypeName.TRIT,
                    expected,
                    expression.location,
                    "comparison result",
                )
            operand_type = self._comparison_operand_type(expression)
            left_type = self._analyze_expression(expression.left, operand_type)
            right_type = self._analyze_expression(expression.right, operand_type)
            self._require_type(
                left_type,
                right_type,
                expression.location,
                "comparison operands",
            )
            return ast.TypeName.TRIT

        operand_type = expected or self._binary_operand_type(expression)
        left_type = self._analyze_expression(expression.left, operand_type)
        right_type = self._analyze_expression(expression.right, operand_type)
        self._require_type(
            left_type,
            right_type,
            expression.location,
            f"operands of '{expression.operator.value}'",
        )
        return left_type

    def _comparison_operand_type(
        self,
        expression: ast.BinaryExpression,
    ) -> ast.TypeName:
        known = self._known_expression_type(expression.left)
        if known is None:
            known = self._known_expression_type(expression.right)
        return known or ast.TypeName.TRYTE

    def _binary_operand_type(self, expression: ast.BinaryExpression) -> ast.TypeName:
        left = self._known_expression_type(expression.left)
        right = self._known_expression_type(expression.right)
        if left is not None and right is not None:
            self._require_type(left, right, expression.location, "binary operands")
        return left or right or ast.TypeName.TRYTE

    def _known_expression_type(
        self,
        expression: ast.Expression,
    ) -> ast.TypeName | None:
        if isinstance(expression, ast.Identifier):
            return self._identifier_type(expression)
        if isinstance(expression, ast.CallExpression):
            signature = self.functions.get(expression.function_name)
            return None if signature is None else signature.return_type
        if isinstance(expression, ast.UnaryExpression):
            return self._known_expression_type(expression.operand)
        if (
            isinstance(expression, ast.BinaryExpression)
            and expression.operator is ast.BinaryOperator.COMPARE
        ):
            return ast.TypeName.TRIT
        return None

    def _lookup_variable(self, name: str) -> ast.TypeName | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def _identifier_type(self, expression: ast.Identifier) -> ast.TypeName:
        result = self._lookup_variable(expression.name)
        if result is not None:
            return result
        if expression.name in self.functions:
            raise SemanticError(
                f"function '{expression.name}' cannot be used as a variable",
                expression.location,
            )
        raise SemanticError(
            f"undeclared variable '{expression.name}'",
            expression.location,
        )

    def _validate_literal(
        self,
        literal: ast.IntegerLiteral,
        type_name: ast.TypeName,
    ) -> None:
        minimum, maximum = (
            (TRIT_MIN, TRIT_MAX)
            if type_name is ast.TypeName.TRIT
            else (TRYTE_MIN, TRYTE_MAX)
        )
        if not minimum <= literal.value <= maximum:
            raise SemanticError(
                f"literal {literal.value} is outside {type_name.value} range "
                f"[{minimum}, {maximum}]",
                literal.location,
            )

    @staticmethod
    def _require_type(
        actual: ast.TypeName,
        expected: ast.TypeName,
        location: SourceLocation,
        subject: str,
    ) -> None:
        if actual is not expected:
            raise SemanticError(
                f"{subject} has type {actual.value}; expected {expected.value}",
                location,
            )


def analyze(program: ast.Program) -> SemanticModel:
    return SemanticAnalyzer().analyze(program)
