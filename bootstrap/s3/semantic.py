"""Two-phase name, type, scope, mutability, and return-path analysis for S3."""

from __future__ import annotations

from dataclasses import dataclass

from . import ast
from .diagnostics import DiagnosticCode, SemanticError, SourceLocation
from .ternary import TRIT_MAX, TRIT_MIN, TRYTE_MAX, TRYTE_MIN


@dataclass(frozen=True, slots=True)
class FunctionType:
    name: str
    parameter_types: tuple[ast.TypeName, ...]
    return_type: ast.TypeName
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Binding:
    type_name: ast.DeclaredType
    mutable: bool
    parameter: bool
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class BlockFlow:
    terminates: bool
    definitely_returns: bool


@dataclass(frozen=True, slots=True)
class SemanticModel:
    """Scalar expression types and the complete file-level function table."""

    expression_types: dict[int, ast.TypeName]
    functions: dict[str, FunctionType]

    def type_of(self, expression: ast.Expression) -> ast.TypeName:
        try:
            return self.expression_types[id(expression)]
        except KeyError as error:
            raise SemanticError(
                "internal error: expression has no scalar semantic type",
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
        self.scopes: list[dict[str, Binding]] = []
        self.parameter_names: set[str] = set()
        self.return_type = ast.TypeName.TRYTE
        self.loop_depth = 0

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
            try:
                self._analyze_function(function)
            except SemanticError as error:
                error.add_diagnostic_context(function=function.name)
                raise
        return SemanticModel(dict(self.expression_types), dict(self.functions))

    def _collect_signatures(self, program: ast.Program) -> None:
        for function in program.functions:
            if function.name in self.functions:
                raise SemanticError(
                    f"duplicate function '{function.name}'",
                    function.location,
                )
            parameter_names: set[str] = set()
            parameter_types: list[ast.TypeName] = []
            for parameter in function.parameters:
                if parameter.name in parameter_names:
                    raise SemanticError(
                        f"duplicate parameter '{parameter.name}'",
                        parameter.location,
                    )
                parameter_names.add(parameter.name)
                if isinstance(parameter.type_name, ast.ArrayType):
                    raise SemanticError(
                        "arrays cannot be function parameters",
                        parameter.location,
                    )
                parameter_types.append(parameter.type_name)
            if isinstance(function.return_type, ast.ArrayType):
                raise SemanticError(
                    "functions cannot return arrays",
                    function.signature.location,
                )
            self.functions[function.name] = FunctionType(
                function.name,
                tuple(parameter_types),
                function.return_type,
                function.signature.location,
            )

    def _analyze_function(self, function: ast.FunctionDeclaration) -> None:
        signature = self.functions[function.name]
        self.return_type = signature.return_type
        self.parameter_names = {parameter.name for parameter in function.parameters}
        self.scopes = [
            {
                parameter.name: Binding(
                    parameter.type_name,
                    mutable=False,
                    parameter=True,
                    location=parameter.location,
                )
                for parameter in function.parameters
            }
        ]
        flow = self._analyze_block(function.body, create_scope=False)
        if not flow.definitely_returns:
            raise SemanticError(
                f"function '{function.name}' has a path without returning "
                f"{self.return_type.value}",
                function.location,
            )

    def _analyze_block(self, block: ast.Block, *, create_scope: bool) -> BlockFlow:
        if create_scope:
            self.scopes.append({})
        block_terminates = False
        definitely_returns = False
        try:
            for statement in block.statements:
                if block_terminates:
                    raise SemanticError(
                        "unreachable statement after return or terminating switch",
                        statement.location,
                    )
                flow = self._analyze_statement(statement)
                if flow.terminates:
                    block_terminates = True
                if flow.definitely_returns:
                    definitely_returns = True
            return BlockFlow(terminates=block_terminates, definitely_returns=definitely_returns)
        finally:
            if create_scope:
                self.scopes.pop()

    def _analyze_statement(self, statement: ast.Statement) -> BlockFlow:
        if isinstance(statement, ast.VariableDeclaration):
            self._analyze_declaration(statement)
            return BlockFlow(terminates=False, definitely_returns=False)
        if isinstance(statement, ast.AssignmentStatement):
            self._analyze_assignment(statement)
            return BlockFlow(terminates=False, definitely_returns=False)
        if isinstance(statement, ast.ReturnStatement):
            if (
                isinstance(statement.expression, ast.Identifier)
                and isinstance(
                    self._lookup_binding(statement.expression.name).type_name
                    if self._lookup_binding(statement.expression.name)
                    else None,
                    ast.ArrayType,
                )
            ):
                raise SemanticError(
                    "arrays cannot be returned",
                    statement.expression.location,
                )
            actual = self._analyze_expression(statement.expression, self.return_type)
            self._require_type(
                actual,
                self.return_type,
                statement.expression.location,
                "returned expression",
            )
            return BlockFlow(terminates=True, definitely_returns=True)
        if isinstance(statement, ast.BreakStatement):
            if self.loop_depth == 0:
                raise SemanticError("break outside loop", statement.location)
            return BlockFlow(terminates=True, definitely_returns=False)
        if isinstance(statement, ast.ContinueStatement):
            if self.loop_depth == 0:
                raise SemanticError("continue outside loop", statement.location)
            return BlockFlow(terminates=True, definitely_returns=False)
        if isinstance(statement, ast.SwitchStatement):
            return self._analyze_switch(statement)
        if isinstance(statement, ast.WhileStatement):
            return self._analyze_while(statement)
        raise SemanticError("unsupported statement", statement.location)

    def _analyze_while(self, statement: ast.WhileStatement) -> BlockFlow:
        condition_type = self._analyze_expression(
            statement.condition,
            ast.TypeName.TRIT,
        )
        self._require_type(
            condition_type,
            ast.TypeName.TRIT,
            statement.condition.location,
            "while condition",
        )
        self.loop_depth += 1
        try:
            self._analyze_block(statement.body, create_scope=True)
        finally:
            self.loop_depth -= 1
        return BlockFlow(terminates=False, definitely_returns=False)

    def _analyze_switch(self, statement: ast.SwitchStatement) -> BlockFlow:
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
        case_flows = [
            self._analyze_block(cases[label].body, create_scope=True)
            for label in (-1, 0, 1)
        ]
        return BlockFlow(
            terminates=all(flow.terminates for flow in case_flows),
            definitely_returns=all(flow.definitely_returns for flow in case_flows),
        )

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

        if isinstance(declaration.type_name, ast.ArrayType):
            self._validate_array_type(declaration.type_name)
            if not isinstance(declaration.initializer, ast.ArrayLiteral):
                raise SemanticError(
                    f"array '{declaration.name}' requires an array literal initializer",
                    declaration.initializer.location,
                )
            self._analyze_array_literal(
                declaration.initializer,
                declaration.type_name,
            )
        else:
            if isinstance(declaration.initializer, ast.ArrayLiteral):
                raise SemanticError(
                    f"scalar '{declaration.name}' cannot use an array initializer",
                    declaration.initializer.location,
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
        current_scope[declaration.name] = Binding(
            declaration.type_name,
            declaration.mutable,
            parameter=False,
            location=declaration.location,
        )

    def _validate_array_type(self, type_name: ast.ArrayType) -> None:
        if isinstance(type_name.element_type, ast.ArrayType):
            raise SemanticError(
                "nested arrays are not supported",
                type_name.location,
            )
        if type_name.length <= 0:
            raise SemanticError(
                f"array length must be positive, got {type_name.length}",
                type_name.location,
            )
        if type_name.length > TRYTE_MAX + 1:
            raise SemanticError(
                f"array length {type_name.length} exceeds tryte-indexed "
                f"maximum {TRYTE_MAX + 1}",
                type_name.location,
            )

    def _analyze_array_literal(
        self,
        literal: ast.ArrayLiteral,
        type_name: ast.ArrayType,
    ) -> None:
        assert isinstance(type_name.element_type, ast.TypeName)
        if len(literal.elements) != type_name.length:
            raise SemanticError(
                f"array initializer has {len(literal.elements)} element(s); "
                f"expected {type_name.length}",
                literal.location,
            )
        for index, element in enumerate(literal.elements):
            actual = self._analyze_expression(element, type_name.element_type)
            self._require_type(
                actual,
                type_name.element_type,
                element.location,
                f"array element {index}",
            )

    def _analyze_assignment(self, statement: ast.AssignmentStatement) -> None:
        if isinstance(statement.target, ast.VariableTarget):
            binding = self._assignment_binding(
                statement.target.name,
                statement.target.location,
            )
            if isinstance(binding.type_name, ast.ArrayType):
                raise SemanticError(
                    "whole-array assignment is not supported",
                    statement.target.location,
                )
            self._require_mutable(binding, statement.target.location)
            if isinstance(statement.value, ast.ArrayLiteral):
                raise SemanticError(
                    "scalar assignment requires a scalar expression",
                    statement.value.location,
                )
            actual = self._analyze_expression(statement.value, binding.type_name)
            self._require_type(
                actual,
                binding.type_name,
                statement.value.location,
                "assigned value",
            )
            return

        binding = self._assignment_binding(
            statement.target.array_name,
            statement.target.location,
        )
        if not isinstance(binding.type_name, ast.ArrayType):
            raise SemanticError(
                f"variable '{statement.target.array_name}' is not an array",
                statement.target.location,
            )
        self._require_mutable(binding, statement.target.location)
        self._analyze_index(
            statement.target.array_name,
            statement.target.index,
            binding.type_name,
        )
        if isinstance(statement.value, ast.ArrayLiteral):
            raise SemanticError(
                "array element assignment requires a scalar expression",
                statement.value.location,
            )
        assert isinstance(binding.type_name.element_type, ast.TypeName)
        actual = self._analyze_expression(
            statement.value,
            binding.type_name.element_type,
        )
        self._require_type(
            actual,
            binding.type_name.element_type,
            statement.value.location,
            "array element assignment",
        )

    def _assignment_binding(self, name: str, location: SourceLocation) -> Binding:
        binding = self._lookup_binding(name)
        if binding is not None:
            return binding
        if name in self.functions:
            raise SemanticError(
                f"function '{name}' cannot be an assignment target",
                location,
            )
        raise SemanticError(f"undeclared variable '{name}'", location)

    @staticmethod
    def _require_mutable(binding: Binding, location: SourceLocation) -> None:
        if binding.parameter:
            raise SemanticError("cannot assign to a parameter", location)
        if not binding.mutable:
            raise SemanticError("cannot assign to immutable variable", location)

    def _analyze_expression(
        self,
        expression: ast.Expression,
        expected: ast.TypeName | None = None,
    ) -> ast.TypeName:
        if isinstance(expression, ast.IntegerLiteral):
            result = expected or ast.TypeName.TRYTE
            self._validate_literal(expression, result)
        elif isinstance(expression, ast.StringLiteral):
            raise SemanticError(
                "string literals are parsed as static literals but runtime "
                "support is not implemented",
                expression.location,
                diagnostic_code=(
                    DiagnosticCode.SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED
                ),
            )
        elif isinstance(expression, ast.Identifier):
            result = self._identifier_type(expression)
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    f"variable '{expression.name}'",
                )
        elif isinstance(expression, ast.IndexExpression):
            binding = self._lookup_binding(expression.array_name)
            if binding is None:
                raise SemanticError(
                    f"undeclared variable '{expression.array_name}'",
                    expression.location,
                )
            if not isinstance(binding.type_name, ast.ArrayType):
                raise SemanticError(
                    f"variable '{expression.array_name}' is not an array",
                    expression.location,
                )
            result = self._analyze_index(
                expression.array_name,
                expression.index,
                binding.type_name,
            )
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    f"array element '{expression.array_name}'",
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

    def _analyze_index(
        self,
        array_name: str,
        index: ast.Expression,
        type_name: ast.ArrayType,
    ) -> ast.TypeName:
        index_type = self._analyze_expression(index, ast.TypeName.TRYTE)
        self._require_type(
            index_type,
            ast.TypeName.TRYTE,
            index.location,
            "array index",
        )
        constant = self._constant_integer(index)
        if constant is not None and not 0 <= constant < type_name.length:
            raise SemanticError(
                f"constant index {constant} is outside array '{array_name}' "
                f"bounds [0, {type_name.length})",
                index.location,
            )
        assert isinstance(type_name.element_type, ast.TypeName)
        return type_name.element_type

    def _analyze_call(self, expression: ast.CallExpression) -> ast.TypeName:
        if self._lookup_binding(expression.function_name) is not None:
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
            zip(expression.arguments, signature.parameter_types, strict=True),
            start=1,
        ):
            if (
                isinstance(argument.expression, ast.Identifier)
                and (
                    binding := self._lookup_binding(argument.expression.name)
                )
                is not None
                and isinstance(binding.type_name, ast.ArrayType)
            ):
                raise SemanticError("arrays cannot be passed as arguments", argument.location)
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
        RELATIONAL_OPERATORS = {
            ast.BinaryOperator.COMPARE,
            ast.BinaryOperator.EQUAL,
            ast.BinaryOperator.NOT_EQUAL,
            ast.BinaryOperator.LESS,
            ast.BinaryOperator.LESS_EQUAL,
            ast.BinaryOperator.GREATER,
            ast.BinaryOperator.GREATER_EQUAL,
        }
        if expression.operator in RELATIONAL_OPERATORS:
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
        if isinstance(expression, ast.IndexExpression):
            binding = self._lookup_binding(expression.array_name)
            if binding is not None and isinstance(binding.type_name, ast.ArrayType):
                element = binding.type_name.element_type
                return element if isinstance(element, ast.TypeName) else None
        if isinstance(expression, ast.CallExpression):
            signature = self.functions.get(expression.function_name)
            return None if signature is None else signature.return_type
        if isinstance(expression, ast.UnaryExpression):
            return self._known_expression_type(expression.operand)
        if (
            isinstance(expression, ast.BinaryExpression)
            and expression.operator in (
                ast.BinaryOperator.COMPARE,
                ast.BinaryOperator.EQUAL,
                ast.BinaryOperator.NOT_EQUAL,
                ast.BinaryOperator.LESS,
                ast.BinaryOperator.LESS_EQUAL,
                ast.BinaryOperator.GREATER,
                ast.BinaryOperator.GREATER_EQUAL,
            )
        ):
            return ast.TypeName.TRIT
        return None

    def _lookup_binding(self, name: str) -> Binding | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def _identifier_type(self, expression: ast.Identifier) -> ast.TypeName:
        binding = self._lookup_binding(expression.name)
        if binding is not None:
            if isinstance(binding.type_name, ast.ArrayType):
                raise SemanticError(
                    f"array '{expression.name}' cannot be used as a scalar value",
                    expression.location,
                )
            return binding.type_name
        if expression.name in self.functions:
            raise SemanticError(
                f"function '{expression.name}' cannot be used as a variable",
                expression.location,
            )
        raise SemanticError(
            f"undeclared variable '{expression.name}'",
            expression.location,
        )

    @staticmethod
    def _constant_integer(expression: ast.Expression) -> int | None:
        if isinstance(expression, ast.IntegerLiteral):
            return expression.value
        if isinstance(expression, ast.UnaryExpression):
            operand = SemanticAnalyzer._constant_integer(expression.operand)
            return None if operand is None else -operand
        if isinstance(expression, ast.BinaryExpression):
            left = SemanticAnalyzer._constant_integer(expression.left)
            right = SemanticAnalyzer._constant_integer(expression.right)
            if left is None or right is None:
                return None
            if expression.operator is ast.BinaryOperator.ADD:
                return left + right
            if expression.operator is ast.BinaryOperator.SUBTRACT:
                return left - right
        return None

    @staticmethod
    def _validate_literal(
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
