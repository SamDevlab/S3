"""Two-phase name, type, scope, mutability, and return-path analysis for S3."""

from __future__ import annotations

from dataclasses import dataclass

from . import ast
from .diagnostics import DiagnosticCode, SemanticError, SourceLocation
from .static_text import StaticTextDecodeError, decode_static_text
from .ternary import (
    TRIT_MAX,
    TRIT_MIN,
    TRYTE_MAX,
    TRYTE_MIN,
    TernaryRangeError,
    TernaryWidth,
    add,
    compare,
    invert,
    tritwise_max,
    tritwise_min,
)


STATIC_TEXT_QUERY_BUILTINS = {
    "contains": ast.TypeName.TRIT,
    "starts_with": ast.TypeName.TRIT,
    "ends_with": ast.TypeName.TRIT,
    "find": ast.TypeName.TRYTE,
}

STATIC_TEXT_TRANSFORM_BUILTINS = {
    "upper": 1,
    "lower": 1,
    "trim": 1,
    "repeat": 2,
    "replace": 3,
}


@dataclass(frozen=True, slots=True)
class FunctionType:
    name: str
    parameter_types: tuple[ast.DeclaredType, ...]
    return_type: ast.DeclaredType
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class RecordType:
    name: str
    fields: tuple[ast.RecordField, ...]
    location: SourceLocation

    def field(self, name: str) -> ast.RecordField | None:
        for field in self.fields:
            if field.name == name:
                return field
        return None


@dataclass(frozen=True, slots=True)
class EnumType:
    name: str
    variants: tuple[ast.EnumVariant, ...]
    location: SourceLocation

    def variant(self, name: str) -> ast.EnumVariant | None:
        for variant in self.variants:
            if variant.name == name:
                return variant
        return None

    def discriminant(self, name: str) -> int:
        for index, variant in enumerate(self.variants):
            if variant.name == name:
                return index
        raise KeyError(name)


@dataclass(frozen=True, slots=True)
class Binding:
    type_name: ast.DeclaredType
    mutable: bool
    parameter: bool
    location: SourceLocation
    static_text: str | None = None
    constant_value: int | None = None


@dataclass(frozen=True, slots=True)
class BlockFlow:
    terminates: bool
    definitely_returns: bool


@dataclass(frozen=True, slots=True)
class SemanticModel:
    """Expression types and the complete file-level function table."""

    expression_types: dict[int, ast.DeclaredType]
    functions: dict[str, FunctionType]
    records: dict[str, RecordType]
    enums: dict[str, EnumType]
    static_text_values: dict[int, str]
    constant_values: dict[int, int]
    simplified_expressions: dict[int, ast.Expression]

    def type_of(self, expression: ast.Expression) -> ast.TypeName:
        try:
            result = self.expression_types[id(expression)]
            assert isinstance(result, ast.TypeName)
            return result
        except (KeyError, AssertionError) as error:
            raise SemanticError(
                "internal error: expression has no scalar semantic type",
                expression.location,
            ) from error

    def declared_type_of(self, expression: ast.Expression) -> ast.DeclaredType:
        try:
            return self.expression_types[id(expression)]
        except KeyError as error:
            raise SemanticError(
                "internal error: expression has no semantic type",
                expression.location,
            ) from error

    def array_type_of(self, expression: ast.Expression) -> ast.ArrayType:
        try:
            result = self.expression_types[id(expression)]
            assert isinstance(result, ast.ArrayType)
            return result
        except (KeyError, AssertionError) as error:
            raise SemanticError(
                "internal error: expression has no array semantic type",
                expression.location,
            ) from error

    def static_text_of(self, expression: ast.Expression) -> str | None:
        return self.static_text_values.get(id(expression))

    def constant_value_of(self, expression: ast.Expression) -> int | None:
        return self.constant_values.get(id(expression))

    def simplified_expression_of(self, expression: ast.Expression) -> ast.Expression | None:
        current = expression
        target = None
        while id(current) in self.simplified_expressions:
            current = self.simplified_expressions[id(current)]
            target = current
        return target

    def function(self, name: str) -> FunctionType:
        try:
            return self.functions[name]
        except KeyError as error:
            raise SemanticError(f"unknown function '{name}'") from error

    def record(self, name: str) -> RecordType:
        try:
            return self.records[name]
        except KeyError as error:
            raise SemanticError(f"unknown record type '{name}'") from error

    def enum(self, name: str) -> EnumType:
        try:
            return self.enums[name]
        except KeyError as error:
            raise SemanticError(f"unknown enum type '{name}'") from error

    def is_enum_type(self, type_name: ast.DeclaredType) -> bool:
        return isinstance(type_name, ast.NominalType) and type_name.name in self.enums

    def is_record_type(self, type_name: ast.DeclaredType) -> bool:
        return isinstance(type_name, ast.NominalType) and type_name.name in self.records


class SemanticAnalyzer:
    def __init__(self) -> None:
        self.expression_types: dict[int, ast.DeclaredType] = {}
        self.static_text_values: dict[int, str] = {}
        self.constant_values: dict[int, int] = {}
        self.simplified_expressions: dict[int, ast.Expression] = {}
        self.functions: dict[str, FunctionType] = {}
        self.records: dict[str, RecordType] = {}
        self.enums: dict[str, EnumType] = {}
        self.scopes: list[dict[str, Binding]] = []
        self.parameter_names: set[str] = set()
        self.return_type: ast.DeclaredType = ast.TypeName.TRYTE
        self.loop_depth = 0

    def analyze(self, program: ast.Program) -> SemanticModel:
        self._collect_enums(program)
        self._collect_records(program)
        self._collect_signatures(program)
        if "main" not in self.functions:
            raise SemanticError("program must declare a 'main' function", program.location)
        main = self.functions["main"]
        if main.parameter_types:
            raise SemanticError(
                "entry function 'main' must not declare parameters",
                main.location,
            )
        if main.return_type is ast.TypeName.STRING:
            raise SemanticError(
                "entry function 'main' cannot return string",
                main.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_RETURN_TYPE,
            )
        for function in program.functions:
            try:
                self._analyze_function(function)
            except SemanticError as error:
                error.add_diagnostic_context(function=function.name)
                raise
        return SemanticModel(
            dict(self.expression_types),
            dict(self.functions),
            dict(self.records),
            dict(self.enums),
            dict(self.static_text_values),
            dict(self.constant_values),
            dict(self.simplified_expressions),
        )

    def _collect_enums(self, program: ast.Program) -> None:
        for enum in program.enums:
            if enum.name in self.enums or enum.name in self.records:
                raise SemanticError(
                    f"duplicate type '{enum.name}'",
                    enum.location,
                    diagnostic_code=DiagnosticCode.TYPE_DUPLICATE,
                )
            if len(enum.variants) > TRYTE_MAX + 1:
                raise SemanticError(
                    (
                        f"enum '{enum.name}' has {len(enum.variants)} variants; "
                        f"at most {TRYTE_MAX + 1} fit the tryte discriminant range"
                    ),
                    enum.location,
                )
            variant_names: set[str] = set()
            for variant in enum.variants:
                if variant.name in variant_names:
                    raise SemanticError(
                        f"duplicate variant '{variant.name}' in enum '{enum.name}'",
                        variant.location,
                        diagnostic_code=DiagnosticCode.ENUM_VARIANT_DUPLICATE,
                    )
                variant_names.add(variant.name)
            self.enums[enum.name] = EnumType(
                enum.name,
                enum.variants,
                enum.location,
            )

    def _collect_records(self, program: ast.Program) -> None:
        for record in program.records:
            if record.name in self.records or record.name in self.enums:
                raise SemanticError(
                    f"duplicate type '{record.name}'",
                    record.location,
                    diagnostic_code=DiagnosticCode.TYPE_DUPLICATE,
                )
            field_names: set[str] = set()
            for field in record.fields:
                if field.name in field_names:
                    raise SemanticError(
                        f"duplicate field '{field.name}' in record '{record.name}'",
                        field.location,
                        diagnostic_code=DiagnosticCode.RECORD_FIELD_DUPLICATE,
                    )
                field_names.add(field.name)
                if isinstance(field.type_name, ast.ArrayType):
                    raise SemanticError(
                        "record fields cannot be arrays in milestone 1.00",
                        field.location,
                    )
                if field.type_name is ast.TypeName.STRING:
                    raise SemanticError(
                        "record fields cannot be string in milestone 1.00",
                        field.location,
                    )
                if isinstance(field.type_name, ast.NominalType):
                    if field.type_name.name in self.enums:
                        continue
                    raise SemanticError(
                        "nested record fields are not supported yet",
                        field.location,
                    )
            self.records[record.name] = RecordType(
                record.name,
                record.fields,
                record.location,
            )

    def _collect_signatures(self, program: ast.Program) -> None:
        for function in program.functions:
            if function.name in self.records or function.name in self.enums:
                raise SemanticError(
                    f"function '{function.name}' conflicts with type '{function.name}'",
                    function.location,
                    diagnostic_code=DiagnosticCode.TYPE_DUPLICATE,
                )
            if function.name in self.functions:
                raise SemanticError(
                    f"duplicate function '{function.name}'",
                    function.location,
                )
            parameter_names: set[str] = set()
            parameter_types: list[ast.DeclaredType] = []
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
                if isinstance(parameter.type_name, ast.NominalType):
                    if (
                        parameter.type_name.name not in self.records
                        and parameter.type_name.name not in self.enums
                    ):
                        raise SemanticError(
                            f"unknown type '{parameter.type_name.name}'",
                            parameter.location,
                        )
                parameter_types.append(parameter.type_name)
            if isinstance(function.return_type, ast.ArrayType):
                raise SemanticError(
                    "functions cannot return arrays",
                    function.signature.location,
                )
            if isinstance(function.return_type, ast.NominalType):
                if function.return_type.name in self.records:
                    record = self.records[function.return_type.name]
                    if len(record.fields) != 1:
                        raise SemanticError(
                            "multi-field record returns require a future aggregate ABI",
                            function.signature.location,
                        )
                elif function.return_type.name not in self.enums:
                    raise SemanticError(
                        f"unknown type '{function.return_type.name}'",
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
                f"{_type_display(self.return_type)}",
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
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_RETURN_TYPE,
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
        if isinstance(statement, ast.AssignmentStatement):
            return self._analyze_assignment(statement)
        if isinstance(statement, ast.CompoundAssignmentStatement):
            return self._analyze_compound_assignment(statement)
        if isinstance(statement, ast.DiscardStatement):
            self._analyze_expression(statement.expression, None)
            return BlockFlow(definitely_returns=False, terminates=False)
        if isinstance(statement, ast.SwitchStatement):
            return self._analyze_switch(statement)
        if isinstance(statement, ast.WhileStatement):
            return self._analyze_while(statement)
        if isinstance(statement, ast.ForStatement):
            return self._analyze_for(statement)
        raise SemanticError("unsupported statement", statement.location)

    def _analyze_for(self, statement: ast.ForStatement) -> BlockFlow:
        start_type = self._analyze_expression(
            statement.start_expression,
            ast.TypeName.TRYTE,
        )
        self._require_type(
            start_type,
            ast.TypeName.TRYTE,
            statement.start_expression.location,
            "for loop range start bound",
        )
        end_type = self._analyze_expression(
            statement.end_expression,
            ast.TypeName.TRYTE,
        )
        self._require_type(
            end_type,
            ast.TypeName.TRYTE,
            statement.end_expression.location,
            "for loop range end bound",
        )
        step_type = self._analyze_expression(
            statement.step_expression,
            ast.TypeName.TRYTE,
        )
        self._require_type(
            step_type,
            ast.TypeName.TRYTE,
            statement.step_expression.location,
            "for loop range step",
        )
        if isinstance(statement.step_expression, ast.IntegerLiteral) and statement.step_expression.value == 0:
            raise SemanticError(
                "range step cannot be zero",
                statement.step_expression.location,
            )
        self._require_type(
            statement.variable_type,
            ast.TypeName.TRYTE,
            statement.location,
            "for loop variable type",
        )
        self.scopes.append({})
        current_scope = self.scopes[-1]
        current_scope[statement.variable_name] = Binding(
            statement.variable_type,
            mutable=False,
            parameter=False,
            location=statement.location,
        )
        self.loop_depth += 1
        try:
            self._analyze_block(statement.body, create_scope=False)
        finally:
            self.loop_depth -= 1
            self.scopes.pop()
        return BlockFlow(definitely_returns=False, terminates=False)

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
        selector_known = self._known_expression_type(statement.expression)
        if isinstance(selector_known, ast.NominalType) and self._is_enum_type(
            selector_known,
        ):
            selector_type = self._analyze_expression(
                statement.expression,
                selector_known,
            )
            assert isinstance(selector_type, ast.NominalType)
            return self._analyze_enum_switch(statement, selector_type)

        selector_type = self._analyze_expression(statement.expression, ast.TypeName.TRIT)
        self._require_type(
            selector_type,
            ast.TypeName.TRIT,
            statement.expression.location,
            "switch expression",
        )
        explicit_cases: dict[int, ast.TernaryCase] = {}
        fallback_case: ast.TernaryCase | None = None
        for i, case in enumerate(statement.cases):
            if case.label is None:
                if fallback_case is not None:
                    raise SemanticError(
                        "duplicate fallback arm in match statement",
                        case.location,
                    )
                if i != len(statement.cases) - 1:
                    raise SemanticError(
                        "fallback arm must be the last arm in match statement",
                        case.location,
                    )
                fallback_case = case
            else:
                if fallback_case is not None:
                    raise SemanticError(
                        "explicit case arm after fallback arm in match statement",
                        case.location,
                    )
                if case.label not in {-1, 0, 1}:
                    raise SemanticError(
                        f"invalid ternary case {case.label}; expected -1, 0, or 1",
                        case.location,
                    )
                if case.label in explicit_cases:
                    raise SemanticError(
                        f"duplicate ternary case {case.label}",
                        case.location,
                    )
                explicit_cases[case.label] = case

        if fallback_case is not None and len(explicit_cases) == 3:
            raise SemanticError(
                "redundant fallback arm in match statement",
                fallback_case.location,
            )

        cases_by_label: dict[int, ast.TernaryCase] = {}
        for label in (-1, 0, 1):
            if label in explicit_cases:
                cases_by_label[label] = explicit_cases[label]
            elif fallback_case is not None:
                cases_by_label[label] = fallback_case
            else:
                missing = sorted({-1, 0, 1} - explicit_cases.keys())
                rendered = ", ".join(str(lbl) for lbl in missing)
                raise SemanticError(
                    f"ternary switch is missing case(s): {rendered}",
                    statement.location,
                )

        case_flows = [
            self._analyze_block(cases_by_label[label].body, create_scope=True)
            for label in (-1, 0, 1)
        ]
        return BlockFlow(
            terminates=all(flow.terminates for flow in case_flows),
            definitely_returns=all(flow.definitely_returns for flow in case_flows),
        )

    def _analyze_enum_switch(
        self,
        statement: ast.SwitchStatement,
        selector_type: ast.NominalType,
    ) -> BlockFlow:
        enum = self.enums[selector_type.name]
        explicit_cases: dict[int, ast.TernaryCase] = {}
        fallback_case: ast.TernaryCase | None = None
        for i, case in enumerate(statement.cases):
            if case.label is None:
                if fallback_case is not None:
                    raise SemanticError(
                        "duplicate fallback arm in enum match statement",
                        case.location,
                    )
                if i != len(statement.cases) - 1:
                    raise SemanticError(
                        "fallback arm must be the last arm in enum match statement",
                        case.location,
                    )
                fallback_case = case
                continue
            discriminant = self._enum_case_discriminant(
                case.label,
                selector_type,
                case.location,
                "enum match statement",
            )
            if discriminant in explicit_cases:
                raise SemanticError(
                    f"duplicate enum match arm for discriminant {discriminant}",
                    case.location,
                    diagnostic_code=DiagnosticCode.MATCH_DUPLICATE_ARM,
                )
            explicit_cases[discriminant] = case

        if fallback_case is not None and len(explicit_cases) == len(enum.variants):
            raise SemanticError(
                "redundant fallback arm in enum match statement",
                fallback_case.location,
            )

        cases_by_label: dict[int, ast.TernaryCase] = {}
        missing: list[str] = []
        for variant in enum.variants:
            discriminant = enum.discriminant(variant.name)
            if discriminant in explicit_cases:
                cases_by_label[discriminant] = explicit_cases[discriminant]
            elif fallback_case is not None:
                cases_by_label[discriminant] = fallback_case
            else:
                missing.append(f"{enum.name}.{variant.name}")
        if missing:
            raise SemanticError(
                "enum match statement is missing case(s): " + ", ".join(missing),
                statement.location,
                diagnostic_code=DiagnosticCode.MATCH_NON_EXHAUSTIVE,
            )

        case_flows = [
            self._analyze_block(cases_by_label[enum.discriminant(variant.name)].body, create_scope=True)
            for variant in enum.variants
        ]
        return BlockFlow(
            terminates=all(flow.terminates for flow in case_flows),
            definitely_returns=all(flow.definitely_returns for flow in case_flows),
        )

    def _enum_case_discriminant(
        self,
        label: ast.MatchCaseLabel,
        selector_type: ast.NominalType,
        location: SourceLocation,
        context: str,
    ) -> int:
        if isinstance(label, int):
            raise SemanticError(
                f"{context} requires enum variant labels",
                location,
                diagnostic_code=DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
            )
        assert isinstance(label, ast.FieldAccessExpression)
        label_type = self._analyze_expression(label, selector_type)
        self._require_type(
            label_type,
            selector_type,
            label.location,
            f"{context} label",
        )
        discriminant = self.constant_values.get(id(label))
        assert discriminant is not None
        return discriminant

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

        static_text: str | None = None
        constant_value: int | None = None
        self._validate_declared_type(declaration.type_name)
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
            if (
                declaration.type_name is ast.TypeName.STRING
                and not declaration.mutable
                and self._is_constant_static_text_expression(declaration.initializer)
            ):
                static_text = self._constant_static_text_value(
                    declaration.initializer,
                    "string initializer requires a compile-time static text expression",
                )
            elif (
                declaration.type_name in (ast.TypeName.TRIT, ast.TypeName.TRYTE)
                and not declaration.mutable
            ):
                constant_value = self.constant_values.get(id(declaration.initializer))
        current_scope[declaration.name] = Binding(
            declaration.type_name,
            declaration.mutable,
            parameter=False,
            location=declaration.location,
            static_text=static_text,
            constant_value=constant_value,
        )

    def _validate_declared_type(self, type_name: ast.DeclaredType) -> None:
        if (
            isinstance(type_name, ast.NominalType)
            and type_name.name not in self.records
            and type_name.name not in self.enums
        ):
            raise SemanticError(
                f"unknown type '{type_name.name}'",
                type_name.location,
            )

    def _validate_array_type(self, type_name: ast.ArrayType) -> None:
        if isinstance(type_name.element_type, ast.ArrayType):
            raise SemanticError(
                "nested arrays are not supported",
                type_name.location,
            )
        if type_name.element_type is ast.TypeName.STRING:
            raise SemanticError(
                "arrays of string are not supported in milestone 0.53",
                type_name.location,
            )
        if isinstance(type_name.element_type, ast.NominalType):
            raise SemanticError(
                "arrays of nominal types are not supported",
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
            if binding.type_name is ast.TypeName.STRING:
                raise SemanticError(
                    "string indexing is not supported",
                    statement.target.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
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

    def _analyze_compound_assignment(
        self,
        statement: ast.CompoundAssignmentStatement,
    ) -> BlockFlow:
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
            assert isinstance(binding.type_name, ast.TypeName)
            self._reject_string_operation(
                binding.type_name,
                statement.location,
                "compound assignment is not supported for string values",
            )
            actual = self._analyze_expression(statement.value, binding.type_name)
            self._require_type(
                actual,
                binding.type_name,
                statement.value.location,
                "assigned value",
            )
            return BlockFlow(definitely_returns=False, terminates=False)

        binding = self._assignment_binding(
            statement.target.array_name,
            statement.target.location,
        )
        if not isinstance(binding.type_name, ast.ArrayType):
            if binding.type_name is ast.TypeName.STRING:
                raise SemanticError(
                    "string indexing is not supported",
                    statement.target.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
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
        return BlockFlow(definitely_returns=False, terminates=False)

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
        expected: ast.DeclaredType | None = None,
    ) -> ast.DeclaredType:
        if isinstance(expression, ast.IntegerLiteral):
            result = (
                expected
                if expected in (ast.TypeName.TRIT, ast.TypeName.TRYTE)
                else ast.TypeName.TRYTE
            )
            self._validate_literal(expression, result)
            self.constant_values[id(expression)] = expression.value
        elif isinstance(expression, ast.StringLiteral):
            self._validate_static_string_literal(expression)
            self.static_text_values[id(expression)] = decode_static_text(
                expression.value
            )
            result = ast.TypeName.STRING
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    "string literal",
                )
        elif isinstance(expression, ast.Identifier):
            result = self._identifier_type(expression)
            binding = self._lookup_binding(expression.name)
            if binding is not None and binding.static_text is not None:
                self.static_text_values[id(expression)] = binding.static_text
            if binding is not None and binding.constant_value is not None:
                self.constant_values[id(expression)] = binding.constant_value
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    f"variable '{expression.name}'",
                )
        elif isinstance(expression, ast.IndexExpression):
            array_binding = self._index_expression_array_binding(expression)
            if array_binding is not None:
                result = self._analyze_index(
                    expression.array_name,
                    expression.index,
                    array_binding.type_name,
                )
            else:
                target_type = self._known_expression_type(expression.target)
                if target_type is ast.TypeName.STRING:
                    text = self._constant_static_text_value(
                        expression,
                        "string indexing requires a compile-time static text expression",
                    )
                    self.static_text_values[id(expression)] = text
                    result = ast.TypeName.STRING
                elif isinstance(expression.target, ast.Identifier):
                    raise SemanticError(
                        f"variable '{expression.target.name}' is not an array",
                        expression.location,
                    )
                else:
                    result = self._analyze_expression(expression.target)
                    raise SemanticError(
                        f"indexed target has type {result.value}; expected array or compile-time static text",
                        expression.target.location,
                    )
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    "index expression",
                )
        elif isinstance(expression, ast.SliceExpression):
            if isinstance(expression.target, ast.Identifier):
                binding = self._lookup_binding(expression.target.name)
                if binding is not None and isinstance(binding.type_name, ast.ArrayType):
                    raise SemanticError(
                        "array slicing is not supported",
                        expression.location,
                    )
            text = self._constant_static_text_value(
                expression,
                "static text slicing requires a compile-time static text expression",
            )
            self.static_text_values[id(expression)] = text
            result = ast.TypeName.STRING
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    "slice expression",
                )
        elif isinstance(expression, ast.CallExpression):
            result = self._analyze_call(expression)
            if expected is not None:
                call_context = "call expression"
                if expression.simple_function_name is not None:
                    call_context = f"call to '{expression.function_name}'"
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    call_context,
                )
        elif isinstance(expression, ast.RecordExpression):
            result = self._analyze_record_expression(expression)
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    f"record literal '{expression.type_name}'",
                )
        elif isinstance(expression, ast.FieldAccessExpression):
            result = self._analyze_field_access(expression)
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    f"field '{expression.field_name}'",
                )
        elif isinstance(expression, ast.UnaryExpression):
            result = self._analyze_expression(expression.operand, expected)
            self._reject_string_operation(
                result,
                expression.location,
                f"operator '{expression.operator.value}' is not supported for string values",
            )
            self._fold_unary_constant(expression, result)
            self._simplify_unary_expression(expression)
        elif isinstance(expression, ast.BinaryExpression):
            result = self._analyze_binary(expression, expected)
        elif isinstance(expression, ast.MatchExpression):
            result = self._analyze_match_expression(expression, expected)
        elif isinstance(expression, ast.LenExpression):
            result = self._analyze_len(expression, expected)
        else:
            raise SemanticError("unsupported expression", expression.location)
        self.expression_types[id(expression)] = result
        return result

    def _analyze_record_expression(
        self,
        expression: ast.RecordExpression,
    ) -> ast.NominalType:
        record = self.records.get(expression.type_name)
        if record is None:
            raise SemanticError(
                f"unknown record type '{expression.type_name}'",
                expression.location,
            )
        fields_by_name = {field.name: field for field in record.fields}
        seen: set[str] = set()
        for value in expression.fields:
            if value.name in seen:
                raise SemanticError(
                    f"duplicate field '{value.name}' in record literal",
                    value.location,
                    diagnostic_code=DiagnosticCode.RECORD_FIELD_DUPLICATE,
                )
            seen.add(value.name)
            field = fields_by_name.get(value.name)
            if field is None:
                raise SemanticError(
                    f"record '{record.name}' has no field '{value.name}'",
                    value.location,
                    diagnostic_code=DiagnosticCode.RECORD_FIELD_UNKNOWN,
                )
            actual = self._analyze_expression(value.expression, field.type_name)
            self._require_type(
                actual,
                field.type_name,
                value.location,
                f"field '{value.name}'",
            )
        missing = [field.name for field in record.fields if field.name not in seen]
        if missing:
            raise SemanticError(
                (
                    f"record '{record.name}' literal is missing field(s): "
                    + ", ".join(missing)
                ),
                expression.location,
                diagnostic_code=DiagnosticCode.RECORD_FIELD_MISSING,
            )
        return ast.NominalType(record.name, expression.location)

    def _analyze_field_access(
        self,
        expression: ast.FieldAccessExpression,
    ) -> ast.DeclaredType:
        enum_access = self._enum_variant_access(expression)
        if enum_access is not None:
            enum, variant = enum_access
            self.constant_values[id(expression)] = enum.discriminant(variant.name)
            return ast.NominalType(enum.name, expression.location)

        if isinstance(expression.target, ast.Identifier):
            binding = self._lookup_binding(expression.target.name)
            if binding is None:
                if expression.target.name in self.records:
                    raise SemanticError(
                        f"type '{expression.target.name}' cannot be used as a value",
                        expression.location,
                    )
                if expression.target.name in self.functions:
                    raise SemanticError(
                        f"function '{expression.target.name}' cannot be used as a value",
                        expression.location,
                    )
            elif isinstance(binding.type_name, ast.ArrayType):
                raise SemanticError(
                    "field access requires a record value",
                    expression.location,
                    diagnostic_code=DiagnosticCode.RECORD_FIELD_UNKNOWN,
                )

        target_type = self._analyze_expression(expression.target)
        if not isinstance(target_type, ast.NominalType):
            raise SemanticError(
                "field access requires a record value",
                expression.location,
                diagnostic_code=DiagnosticCode.RECORD_FIELD_UNKNOWN,
            )
        record = self.records.get(target_type.name)
        if record is None:
            if target_type.name in self.enums:
                raise SemanticError(
                    "field access requires a record value",
                    expression.location,
                    diagnostic_code=DiagnosticCode.RECORD_FIELD_UNKNOWN,
                )
            raise SemanticError(
                f"unknown record type '{target_type.name}'",
                expression.location,
            )
        field = record.field(expression.field_name)
        if field is None:
            raise SemanticError(
                f"record '{record.name}' has no field '{expression.field_name}'",
                expression.location,
                diagnostic_code=DiagnosticCode.RECORD_FIELD_UNKNOWN,
            )
        return field.type_name

    def _enum_variant_access(
        self,
        expression: ast.FieldAccessExpression,
    ) -> tuple[EnumType, ast.EnumVariant] | None:
        if not isinstance(expression.target, ast.Identifier):
            return None
        if self._lookup_binding(expression.target.name) is not None:
            return None
        enum = self.enums.get(expression.target.name)
        if enum is None:
            return None
        variant = enum.variant(expression.field_name)
        if variant is None:
            raise SemanticError(
                f"enum '{enum.name}' has no variant '{expression.field_name}'",
                expression.location,
                diagnostic_code=DiagnosticCode.ENUM_VARIANT_UNKNOWN,
            )
        return enum, variant

    def _index_expression_array_binding(
        self,
        expression: ast.IndexExpression,
    ) -> Binding | None:
        if not isinstance(expression.target, ast.Identifier):
            return None
        binding = self._lookup_binding(expression.target.name)
        if binding is None:
            raise SemanticError(
                f"undeclared variable '{expression.target.name}'",
                expression.location,
            )
        if isinstance(binding.type_name, ast.ArrayType):
            return binding
        return None

    def _analyze_len(
        self,
        expression: ast.LenExpression,
        expected: ast.TypeName | None = None,
    ) -> ast.TypeName:
        array_length: int | None = None
        if self._is_constant_static_text_expression(expression.argument):
            length = self._constant_static_text_length(expression.argument)
            if length > TRYTE_MAX:
                raise SemanticError(
                    f"static text length {length} exceeds tryte maximum {TRYTE_MAX}",
                    expression.argument.location,
                )
            result = ast.TypeName.TRYTE
            if expected is not None:
                self._require_type(
                    result,
                    expected,
                    expression.location,
                    "len expression",
                )
            self.constant_values[id(expression)] = length
            return result
        if isinstance(expression.argument, ast.Identifier):
            binding = self._lookup_binding(expression.argument.name)
            if binding is None:
                raise SemanticError(
                    f"undeclared variable '{expression.argument.name}'",
                    expression.argument.location,
                )
            if not isinstance(binding.type_name, ast.ArrayType):
                if binding.type_name is ast.TypeName.STRING:
                    raise SemanticError(
                        "len() argument must be a static array or a compile-time static text expression",
                        expression.argument.location,
                        diagnostic_code=(
                            DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                        ),
                    )
                raise SemanticError(
                    "len() argument must be a static array or a compile-time static text expression, "
                    f"got '{_type_display(binding.type_name)}'",
                    expression.argument.location,
                )
            self.expression_types[id(expression.argument)] = binding.type_name
            array_length = binding.type_name.length
        elif isinstance(expression.argument, ast.IndexExpression):
            raise SemanticError(
                "len() argument must be a static array or a compile-time static text expression, not an array element",
                expression.argument.location,
            )
        else:
            known_type = self._known_expression_type(expression.argument)
            if known_type is ast.TypeName.STRING:
                raise SemanticError(
                    "len() argument must be a static array or a compile-time static text expression",
                    expression.argument.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            raise SemanticError(
                "len() argument must be a static array or a compile-time static text expression",
                expression.argument.location,
            )
        result = ast.TypeName.TRYTE
        if expected is not None:
            self._require_type(
                result,
                expected,
                expression.location,
                "len expression",
            )
        assert array_length is not None
        self.constant_values[id(expression)] = array_length
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

    def _analyze_call(self, expression: ast.CallExpression) -> ast.DeclaredType:
        if expression.simple_function_name is None:
            raise SemanticError(
                "call target must be an unqualified function name",
                expression.location,
            )
        if self._lookup_binding(expression.function_name) is not None:
            raise SemanticError(
                f"variable '{expression.function_name}' cannot be called",
                expression.location,
            )
        if expression.function_name in STATIC_TEXT_QUERY_BUILTINS:
            return self._analyze_static_text_query_call(expression)
        if expression.function_name in STATIC_TEXT_TRANSFORM_BUILTINS:
            if expression.function_name not in self.functions or self._is_constant_static_text_transform_call(expression):
                return self._analyze_static_text_transform_call(expression)
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
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
            )
        return signature.return_type

    def _analyze_static_text_query_call(
        self,
        expression: ast.CallExpression,
    ) -> ast.TypeName:
        if len(expression.arguments) != 2:
            raise SemanticError(
                f"builtin '{expression.function_name}' expects 2 argument(s), got "
                f"{len(expression.arguments)}",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
            )
        left = self._constant_static_text_value(
            expression.arguments[0].expression,
            f"builtin '{expression.function_name}' requires compile-time static text arguments",
        )
        right = self._constant_static_text_value(
            expression.arguments[1].expression,
            f"builtin '{expression.function_name}' requires compile-time static text arguments",
        )
        if expression.function_name == "contains":
            value = -1 if right in left else 0
        elif expression.function_name == "starts_with":
            value = -1 if left.startswith(right) else 0
        elif expression.function_name == "ends_with":
            value = -1 if left.endswith(right) else 0
        elif expression.function_name == "find":
            value = left.find(right)
            if not TRYTE_MIN <= value <= TRYTE_MAX:
                raise SemanticError(
                    f"find result {value} is outside tryte range [{TRYTE_MIN}, {TRYTE_MAX}]",
                    expression.location,
                )
        else:
            raise SemanticError(
                f"unknown static text builtin '{expression.function_name}'",
                expression.location,
            )
        self.constant_values[id(expression)] = value
        result = STATIC_TEXT_QUERY_BUILTINS[expression.function_name]
        self.expression_types[id(expression)] = result
        return result

    def _is_constant_static_text_transform_call(
        self,
        expression: ast.CallExpression,
    ) -> bool:
        if expression.function_name not in STATIC_TEXT_TRANSFORM_BUILTINS:
            return False
        expected_count = STATIC_TEXT_TRANSFORM_BUILTINS[expression.function_name]
        if len(expression.arguments) != expected_count:
            return False
        if expression.function_name in ("upper", "lower", "trim"):
            return self._is_constant_static_text_expression(expression.arguments[0].expression)
        if expression.function_name == "repeat":
            return (
                self._is_constant_static_text_expression(expression.arguments[0].expression)
                and self._is_constant_tryte_expression(expression.arguments[1].expression)
            )
        if expression.function_name == "replace":
            return all(
                self._is_constant_static_text_expression(argument.expression)
                for argument in expression.arguments
            )
        return False

    def _analyze_static_text_transform_call(
        self,
        expression: ast.CallExpression,
    ) -> ast.TypeName:
        expected_count = STATIC_TEXT_TRANSFORM_BUILTINS[expression.function_name]
        if len(expression.arguments) != expected_count:
            raise SemanticError(
                f"builtin '{expression.function_name}' expects {expected_count} argument(s), got "
                f"{len(expression.arguments)}",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
            )
        name = expression.function_name
        if name in ("upper", "lower", "trim"):
            text = self._constant_static_text_value(
                expression.arguments[0].expression,
                f"builtin '{name}' requires compile-time static text arguments",
            )
            if name == "upper":
                result_text = text.upper()
            elif name == "lower":
                result_text = text.lower()
            else:
                result_text = text.strip()
        elif name == "repeat":
            text = self._constant_static_text_value(
                expression.arguments[0].expression,
                "builtin 'repeat' requires compile-time static text and count arguments",
            )
            count_type = self._analyze_expression(
                expression.arguments[1].expression,
                ast.TypeName.TRYTE,
            )
            self._require_type(
                count_type,
                ast.TypeName.TRYTE,
                expression.arguments[1].expression.location,
                "repeat count argument",
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
            )
            count = self._constant_tryte_value(expression.arguments[1].expression)
            if count is None:
                raise SemanticError(
                    "builtin 'repeat' requires compile-time static text and count arguments",
                    expression.arguments[1].expression.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION,
                )
            if count < 0:
                raise SemanticError(
                    "repeat count must be non-negative",
                    expression.arguments[1].expression.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION,
                )
            result_text = text * count
        elif name == "replace":
            text = self._constant_static_text_value(
                expression.arguments[0].expression,
                "builtin 'replace' requires compile-time static text arguments",
            )
            old = self._constant_static_text_value(
                expression.arguments[1].expression,
                "builtin 'replace' requires compile-time static text arguments",
            )
            new = self._constant_static_text_value(
                expression.arguments[2].expression,
                "builtin 'replace' requires compile-time static text arguments",
            )
            result_text = text.replace(old, new)
        else:
            raise SemanticError(
                f"unknown static text transform builtin '{name}'",
                expression.location,
            )
        self.static_text_values[id(expression)] = result_text
        self.expression_types[id(expression)] = ast.TypeName.STRING
        return ast.TypeName.STRING

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
            left_known = self._known_expression_type(expression.left)
            right_known = self._known_expression_type(expression.right)
            if isinstance(left_known, ast.NominalType) or isinstance(
                right_known,
                ast.NominalType,
            ):
                left_type = self._analyze_expression(expression.left, left_known)
                right_type = self._analyze_expression(expression.right, right_known)
                self._require_type(
                    left_type,
                    right_type,
                    expression.location,
                    "comparison operands",
                )
                if not self._is_enum_type(left_type):
                    raise SemanticError(
                        f"operator '{expression.operator.value}' is not supported for record values",
                        expression.location,
                    )
                if expression.operator not in (
                    ast.BinaryOperator.EQUAL,
                    ast.BinaryOperator.NOT_EQUAL,
                ):
                    raise SemanticError(
                        f"operator '{expression.operator.value}' is not supported for enum values",
                        expression.location,
                    )
                if expected is not None:
                    self._require_type(
                        ast.TypeName.TRIT,
                        expected,
                        expression.location,
                        "enum comparison result",
                    )
                self._fold_binary_constant(expression, ast.TypeName.TRIT)
                return ast.TypeName.TRIT
            if (
                left_known is ast.TypeName.STRING
                or right_known is ast.TypeName.STRING
            ):
                if (
                    self._is_constant_static_text_expression(expression.left)
                    and self._is_constant_static_text_expression(expression.right)
                ):
                    self._validate_constant_static_text_expression(expression.left)
                    self._validate_constant_static_text_expression(expression.right)
                    if expected is not None:
                        self._require_type(
                            ast.TypeName.TRIT,
                            expected,
                            expression.location,
                            "static text comparison result",
                        )
                    left_text = self._constant_static_text_value(
                        expression.left,
                        "string comparison requires compile-time static text expressions",
                    )
                    right_text = self._constant_static_text_value(
                        expression.right,
                        "string comparison requires compile-time static text expressions",
                    )
                    if expression.operator is ast.BinaryOperator.EQUAL:
                        res = left_text == right_text
                    elif expression.operator is ast.BinaryOperator.NOT_EQUAL:
                        res = left_text != right_text
                    elif expression.operator is ast.BinaryOperator.LESS:
                        res = left_text < right_text
                    elif expression.operator is ast.BinaryOperator.LESS_EQUAL:
                        res = left_text <= right_text
                    elif expression.operator is ast.BinaryOperator.GREATER:
                        res = left_text > right_text
                    elif expression.operator is ast.BinaryOperator.GREATER_EQUAL:
                        res = left_text >= right_text
                    else:
                        res = False
                    self.constant_values[id(expression)] = (
                        self._comparison_result(res)
                    )
                    self.expression_types[id(expression)] = ast.TypeName.TRIT
                    return ast.TypeName.TRIT
                if (
                    left_known is not None
                    and right_known is not None
                    and left_known is not right_known
                ):
                    left_type = self._analyze_expression(
                        expression.left,
                        left_known,
                    )
                    right_type = self._analyze_expression(
                        expression.right,
                        right_known,
                    )
                    self._require_type(
                        left_type,
                        right_type,
                        expression.location,
                        "comparison operands",
                    )
                self._analyze_expression(expression.left, left_known)
                self._analyze_expression(expression.right, right_known)
                if expression.operator in (
                    ast.BinaryOperator.EQUAL,
                    ast.BinaryOperator.NOT_EQUAL,
                ):
                    raise SemanticError(
                        "string equality requires compile-time static text expressions",
                        expression.location,
                        diagnostic_code=(
                            DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                        ),
                    )
                raise SemanticError(
                    f"operator '{expression.operator.value}' is not supported for string values",
                    expression.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            operand_type = self._comparison_operand_type(expression)
            self._reject_string_operation(
                operand_type,
                expression.location,
                f"operator '{expression.operator.value}' is not supported for string values",
            )
            if expected is not None:
                self._require_type(
                    ast.TypeName.TRIT,
                    expected,
                    expression.location,
                    "comparison result",
                )
            left_type = self._analyze_expression(expression.left, operand_type)
            right_type = self._analyze_expression(expression.right, operand_type)
            self._require_type(
                left_type,
                right_type,
                expression.location,
                "comparison operands",
            )
            self._fold_binary_constant(expression, ast.TypeName.TRIT)
            return ast.TypeName.TRIT
        if expression.operator is ast.BinaryOperator.ADD:
            left_known = self._known_expression_type(expression.left)
            right_known = self._known_expression_type(expression.right)
            if left_known is ast.TypeName.STRING or right_known is ast.TypeName.STRING:
                if self._is_constant_static_text_expression(expression):
                    self._validate_constant_static_text_expression(expression)
                    if expected is not None:
                        self._require_type(
                            ast.TypeName.STRING,
                            expected,
                            expression.location,
                            "constant static text concatenation",
                        )
                    self.expression_types[id(expression)] = ast.TypeName.STRING
                    return ast.TypeName.STRING
                if (
                    left_known is not None
                    and right_known is not None
                    and left_known is not right_known
                ):
                    left_type = self._analyze_expression(expression.left, left_known)
                    right_type = self._analyze_expression(expression.right, right_known)
                    self._require_type(
                        left_type,
                        right_type,
                        expression.location,
                        "operands of '+'",
                    )
                self._analyze_expression(expression.left, left_known)
                self._analyze_expression(expression.right, right_known)
                raise SemanticError(
                    "string concatenation requires a compile-time static text expression",
                    expression.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION,
                )
        operand_type = self._binary_operand_type(expression)
        if isinstance(operand_type, ast.NominalType):
            self._analyze_expression(expression.left, operand_type)
            self._analyze_expression(expression.right, operand_type)
            raise SemanticError(
                f"operator '{expression.operator.value}' is not supported for nominal values",
                expression.location,
            )
        self._reject_string_operation(
            operand_type,
            expression.location,
            f"operator '{expression.operator.value}' is not supported for string values",
        )
        if expected is not None:
            operand_type = expected
        left_type = self._analyze_expression(expression.left, operand_type)
        right_type = self._analyze_expression(expression.right, operand_type)
        self._require_type(
            left_type,
            right_type,
            expression.location,
            f"operands of '{expression.operator.value}'",
        )
        result_type = (
            ast.TypeName.TRIT
            if expression.operator in RELATIONAL_OPERATORS
            else left_type
        )
        self._fold_binary_constant(expression, result_type)
        self._simplify_binary_expression(expression)
        return left_type

    def _comparison_operand_type(
        self,
        expression: ast.BinaryExpression,
    ) -> ast.DeclaredType:
        left = self._known_expression_type(expression.left)
        right = self._known_expression_type(expression.right)
        if left is ast.TypeName.STRING or right is ast.TypeName.STRING:
            return ast.TypeName.STRING
        return left or right or ast.TypeName.TRYTE

    def _binary_operand_type(self, expression: ast.BinaryExpression) -> ast.DeclaredType:
        left = self._known_expression_type(expression.left)
        right = self._known_expression_type(expression.right)
        if left is ast.TypeName.STRING or right is ast.TypeName.STRING:
            return ast.TypeName.STRING
        if left is not None and right is not None:
            self._require_type(left, right, expression.location, "binary operands")
        return left or right or ast.TypeName.TRYTE

    def _known_expression_type(
        self,
        expression: ast.Expression,
    ) -> ast.DeclaredType | None:
        if isinstance(expression, ast.IntegerLiteral):
            return ast.TypeName.TRYTE
        if isinstance(expression, ast.Identifier):
            return self._identifier_type(expression)
        if isinstance(expression, ast.StringLiteral):
            return ast.TypeName.STRING
        if isinstance(expression, ast.IndexExpression):
            try:
                binding = self._index_expression_array_binding(expression)
            except SemanticError:
                binding = None
            if binding is not None:
                element = binding.type_name.element_type
                return element if isinstance(element, ast.TypeName) else None
            if self._known_expression_type(expression.target) is ast.TypeName.STRING:
                return ast.TypeName.STRING
        if isinstance(expression, ast.SliceExpression):
            target_type = self._known_expression_type(expression.target)
            if target_type is ast.TypeName.STRING:
                return ast.TypeName.STRING
            return target_type
        if isinstance(expression, ast.CallExpression):
            function_name = expression.simple_function_name
            if function_name is None:
                return None
            if function_name in STATIC_TEXT_QUERY_BUILTINS:
                return STATIC_TEXT_QUERY_BUILTINS[function_name]
            if function_name in STATIC_TEXT_TRANSFORM_BUILTINS:
                return ast.TypeName.STRING
            signature = self.functions.get(function_name)
            return None if signature is None else signature.return_type
        if isinstance(expression, ast.RecordExpression):
            if expression.type_name in self.records:
                return ast.NominalType(expression.type_name, expression.location)
            return None
        if isinstance(expression, ast.FieldAccessExpression):
            enum_access = self._enum_variant_access(expression)
            if enum_access is not None:
                enum, _variant = enum_access
                return ast.NominalType(enum.name, expression.location)
            target_type = self._known_expression_type(expression.target)
            if isinstance(target_type, ast.NominalType):
                record = self.records.get(target_type.name)
                if record is not None:
                    field = record.field(expression.field_name)
                    return None if field is None else field.type_name
            return None
        if isinstance(expression, ast.UnaryExpression):
            return self._known_expression_type(expression.operand)
        if (
            isinstance(expression, ast.BinaryExpression)
            and expression.operator
            in (
                ast.BinaryOperator.ADD,
                ast.BinaryOperator.SUBTRACT,
                ast.BinaryOperator.MINIMUM,
                ast.BinaryOperator.MAXIMUM,
            )
        ):
            left = self._known_expression_type(expression.left)
            right = self._known_expression_type(expression.right)
            if left is ast.TypeName.STRING or right is ast.TypeName.STRING:
                return ast.TypeName.STRING
            if left is not None and right is not None and left is right:
                return left
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
        if isinstance(expression, ast.MatchExpression):
            for case in expression.cases:
                known = self._known_expression_type(case.expression)
                if known is not None:
                    return known
            return None
        return None

    def _analyze_match_expression(
        self,
        expression: ast.MatchExpression,
        expected: ast.DeclaredType | None,
    ) -> ast.DeclaredType:
        selector_known = self._known_expression_type(expression.selector)
        if isinstance(selector_known, ast.NominalType) and self._is_enum_type(
            selector_known,
        ):
            selector_type = self._analyze_expression(
                expression.selector,
                selector_known,
            )
            assert isinstance(selector_type, ast.NominalType)
            return self._analyze_enum_match_expression(
                expression,
                selector_type,
                expected,
            )

        selector_type = self._analyze_expression(expression.selector, ast.TypeName.TRIT)
        self._require_type(
            selector_type,
            ast.TypeName.TRIT,
            expression.selector.location,
            "match expression selector",
        )
        explicit_cases: dict[int, ast.MatchExpressionCase] = {}
        fallback_case: ast.MatchExpressionCase | None = None
        for i, case in enumerate(expression.cases):
            if case.label is None:
                if fallback_case is not None:
                    raise SemanticError(
                        "duplicate fallback arm in match expression",
                        case.location,
                    )
                if i != len(expression.cases) - 1:
                    raise SemanticError(
                        "fallback arm must be the last arm in match expression",
                        case.location,
                    )
                fallback_case = case
            else:
                if fallback_case is not None:
                    raise SemanticError(
                        "explicit case arm after fallback arm in match expression",
                        case.location,
                    )
                if case.label not in {-1, 0, 1}:
                    raise SemanticError(
                        f"invalid ternary case {case.label}; expected -1, 0, or 1",
                        case.location,
                    )
                if case.label in explicit_cases:
                    raise SemanticError(
                        f"duplicate ternary case {case.label}",
                        case.location,
                    )
                explicit_cases[case.label] = case

        if fallback_case is not None and len(explicit_cases) == 3:
            raise SemanticError(
                "redundant fallback arm in match expression",
                fallback_case.location,
            )

        cases_by_label: dict[int, ast.MatchExpressionCase] = {}
        for label in (-1, 0, 1):
            if label in explicit_cases:
                cases_by_label[label] = explicit_cases[label]
            elif fallback_case is not None:
                cases_by_label[label] = fallback_case
            else:
                missing = sorted({-1, 0, 1} - explicit_cases.keys())
                rendered = ", ".join(str(lbl) for lbl in missing)
                raise SemanticError(
                    f"match expression is missing case(s): {rendered}",
                    expression.location,
                )

        arm_types: list[ast.DeclaredType] = []
        for label in (-1, 0, 1):
            case = cases_by_label[label]
            arm_expected = expected or (arm_types[0] if arm_types else None)
            arm_type = self._analyze_expression(case.expression, arm_expected)
            if arm_types:
                self._require_type(
                    arm_type,
                    arm_types[0],
                    case.expression.location,
                    "match expression arm",
                )
            arm_types.append(arm_type)

        result_type = arm_types[0]
        self.expression_types[id(expression)] = result_type
        if expected is not None:
            self._require_type(
                result_type,
                expected,
                expression.location,
                "match expression result",
            )
        selector_val = self.constant_values.get(id(expression.selector))
        if selector_val is not None and selector_val in cases_by_label:
            target_case = cases_by_label[selector_val]
            self.simplified_expressions[id(expression)] = target_case.expression
            val = self.constant_values.get(id(target_case.expression))
            if val is not None:
                self.constant_values[id(expression)] = val
            text = self.static_text_values.get(id(target_case.expression))
            if text is not None:
                self.static_text_values[id(expression)] = text
        return result_type

    def _analyze_enum_match_expression(
        self,
        expression: ast.MatchExpression,
        selector_type: ast.NominalType,
        expected: ast.DeclaredType | None,
    ) -> ast.DeclaredType:
        enum = self.enums[selector_type.name]
        explicit_cases: dict[int, ast.MatchExpressionCase] = {}
        fallback_case: ast.MatchExpressionCase | None = None
        for i, case in enumerate(expression.cases):
            if case.label is None:
                if fallback_case is not None:
                    raise SemanticError(
                        "duplicate fallback arm in enum match expression",
                        case.location,
                    )
                if i != len(expression.cases) - 1:
                    raise SemanticError(
                        "fallback arm must be the last arm in enum match expression",
                        case.location,
                    )
                fallback_case = case
                continue
            discriminant = self._enum_case_discriminant(
                case.label,
                selector_type,
                case.location,
                "enum match expression",
            )
            if discriminant in explicit_cases:
                raise SemanticError(
                    f"duplicate enum match arm for discriminant {discriminant}",
                    case.location,
                    diagnostic_code=DiagnosticCode.MATCH_DUPLICATE_ARM,
                )
            explicit_cases[discriminant] = case

        if fallback_case is not None and len(explicit_cases) == len(enum.variants):
            raise SemanticError(
                "redundant fallback arm in enum match expression",
                fallback_case.location,
            )

        cases_by_label: dict[int, ast.MatchExpressionCase] = {}
        missing: list[str] = []
        for variant in enum.variants:
            discriminant = enum.discriminant(variant.name)
            if discriminant in explicit_cases:
                cases_by_label[discriminant] = explicit_cases[discriminant]
            elif fallback_case is not None:
                cases_by_label[discriminant] = fallback_case
            else:
                missing.append(f"{enum.name}.{variant.name}")
        if missing:
            raise SemanticError(
                "enum match expression is missing case(s): " + ", ".join(missing),
                expression.location,
                diagnostic_code=DiagnosticCode.MATCH_NON_EXHAUSTIVE,
            )

        arm_types: list[ast.DeclaredType] = []
        for variant in enum.variants:
            label = enum.discriminant(variant.name)
            case = cases_by_label[label]
            arm_expected = expected or (arm_types[0] if arm_types else None)
            arm_type = self._analyze_expression(case.expression, arm_expected)
            if arm_types:
                self._require_type(
                    arm_type,
                    arm_types[0],
                    case.expression.location,
                    "enum match expression arm",
                )
            arm_types.append(arm_type)

        result_type = arm_types[0]
        self.expression_types[id(expression)] = result_type
        if expected is not None:
            self._require_type(
                result_type,
                expected,
                expression.location,
                "enum match expression result",
            )
        selector_val = self.constant_values.get(id(expression.selector))
        if selector_val is not None and selector_val in cases_by_label:
            target_case = cases_by_label[selector_val]
            self.simplified_expressions[id(expression)] = target_case.expression
            val = self.constant_values.get(id(target_case.expression))
            if val is not None:
                self.constant_values[id(expression)] = val
            text = self.static_text_values.get(id(target_case.expression))
            if text is not None:
                self.static_text_values[id(expression)] = text
        return result_type

    def _lookup_binding(self, name: str) -> Binding | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def _is_enum_type(self, type_name: ast.DeclaredType) -> bool:
        return isinstance(type_name, ast.NominalType) and type_name.name in self.enums

    def _identifier_type(self, expression: ast.Identifier) -> ast.DeclaredType:
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
    def _width(type_name: ast.TypeName) -> TernaryWidth:
        return (
            TernaryWidth.TRIT
            if type_name is ast.TypeName.TRIT
            else TernaryWidth.TRYTE
        )

    @staticmethod
    def _comparison_result(value: bool) -> int:
        return -1 if value else 0

    def _constant_tryte_value(self, expression: ast.Expression) -> int | None:
        if self.expression_types.get(id(expression)) is not ast.TypeName.TRYTE:
            return None
        return self.constant_values.get(id(expression))

    def _is_constant_tryte_expression(self, expression: ast.Expression) -> bool:
        if isinstance(expression, ast.IntegerLiteral):
            return True
        if isinstance(expression, ast.Identifier):
            binding = self._lookup_binding(expression.name)
            return (
                binding is not None
                and binding.type_name is ast.TypeName.TRYTE
                and binding.constant_value is not None
            )
        if isinstance(expression, ast.UnaryExpression):
            return self._is_constant_tryte_expression(expression.operand)
        if (
            isinstance(expression, ast.BinaryExpression)
            and expression.operator
            in (
                ast.BinaryOperator.ADD,
                ast.BinaryOperator.SUBTRACT,
                ast.BinaryOperator.MINIMUM,
                ast.BinaryOperator.MAXIMUM,
            )
        ):
            return (
                self._is_constant_tryte_expression(expression.left)
                and self._is_constant_tryte_expression(expression.right)
            )
        if isinstance(expression, ast.LenExpression):
            if self._is_constant_static_text_expression(expression.argument):
                return True
            if isinstance(expression.argument, ast.Identifier):
                binding = self._lookup_binding(expression.argument.name)
                return binding is not None and isinstance(binding.type_name, ast.ArrayType)
        if isinstance(expression, ast.CallExpression):
            if expression.simple_function_name is None:
                return False
            return (
                expression.function_name == "find"
                and len(expression.arguments) == 2
                and all(
                    self._is_constant_static_text_expression(argument.expression)
                    for argument in expression.arguments
                )
            )
        return False

    def _fold_unary_constant(
        self,
        expression: ast.UnaryExpression,
        result_type: ast.TypeName,
    ) -> None:
        operand = self.constant_values.get(id(expression.operand))
        if operand is None:
            return
        try:
            value = invert(operand, self._width(result_type))
        except TernaryRangeError as error:
            raise SemanticError(str(error), expression.location) from error
        self.constant_values[id(expression)] = value

    def _fold_binary_constant(
        self,
        expression: ast.BinaryExpression,
        result_type: ast.TypeName,
    ) -> None:
        left = self.constant_values.get(id(expression.left))
        right = self.constant_values.get(id(expression.right))
        if left is None or right is None:
            return
        try:
            if expression.operator is ast.BinaryOperator.ADD:
                value = add(left, right, self._width(result_type))
            elif expression.operator is ast.BinaryOperator.SUBTRACT:
                width = self._width(result_type)
                value = add(left, invert(right, width), width)
            elif expression.operator is ast.BinaryOperator.MINIMUM:
                value = tritwise_min(left, right, self._width(result_type))
            elif expression.operator is ast.BinaryOperator.MAXIMUM:
                value = tritwise_max(left, right, self._width(result_type))
            elif expression.operator is ast.BinaryOperator.COMPARE:
                source_type = self.expression_types.get(id(expression.left))
                assert isinstance(source_type, ast.TypeName)
                value = compare(left, right, self._width(source_type))
            elif expression.operator is ast.BinaryOperator.EQUAL:
                value = self._comparison_result(left == right)
            elif expression.operator is ast.BinaryOperator.NOT_EQUAL:
                value = self._comparison_result(left != right)
            elif expression.operator is ast.BinaryOperator.LESS:
                value = self._comparison_result(left < right)
            elif expression.operator is ast.BinaryOperator.LESS_EQUAL:
                value = self._comparison_result(left <= right)
            elif expression.operator is ast.BinaryOperator.GREATER:
                value = self._comparison_result(left > right)
            elif expression.operator is ast.BinaryOperator.GREATER_EQUAL:
                value = self._comparison_result(left >= right)
            else:
                return
        except TernaryRangeError as error:
            raise SemanticError(str(error), expression.location) from error
        self.constant_values[id(expression)] = value

    def _simplify_binary_expression(self, expression: ast.BinaryExpression) -> None:
        left_const = self.constant_values.get(id(expression.left))
        right_const = self.constant_values.get(id(expression.right))
        if expression.operator is ast.BinaryOperator.ADD:
            if right_const == 0:
                self.simplified_expressions[id(expression)] = expression.left
            elif left_const == 0:
                self.simplified_expressions[id(expression)] = expression.right
        elif expression.operator is ast.BinaryOperator.SUBTRACT:
            if right_const == 0:
                self.simplified_expressions[id(expression)] = expression.left
        elif expression.operator is ast.BinaryOperator.MINIMUM:
            if right_const == TRYTE_MAX:
                self.simplified_expressions[id(expression)] = expression.left
            elif left_const == TRYTE_MAX:
                self.simplified_expressions[id(expression)] = expression.right
        elif expression.operator is ast.BinaryOperator.MAXIMUM:
            if right_const == TRYTE_MIN:
                self.simplified_expressions[id(expression)] = expression.left
            elif left_const == TRYTE_MIN:
                self.simplified_expressions[id(expression)] = expression.right


    def _simplify_unary_expression(self, expression: ast.UnaryExpression) -> None:
        if isinstance(expression.operand, ast.UnaryExpression):
            if expression.operator is expression.operand.operator:
                if expression.operator in (ast.UnaryOperator.INVERT, ast.UnaryOperator.NEGATE):
                    self.simplified_expressions[id(expression)] = expression.operand.operand

    @staticmethod
    def _validate_static_string_literal(literal: ast.StringLiteral) -> None:
        try:
            decode_static_text(literal.value)
        except StaticTextDecodeError as error:
            raise SemanticError(
                str(error),
                literal.location,
            ) from error

    def _validate_constant_static_text_expression(
        self,
        expression: ast.Expression,
    ) -> None:
        self._constant_static_text_value(
            expression,
            "string concatenation requires a compile-time static text expression",
        )

    def _constant_static_text_length(self, expression: ast.Expression) -> int:
        return len(
            self._constant_static_text_value(
                expression,
                "len() argument must be a static array or a compile-time static text expression",
            )
        )

    def _constant_static_text_value(
        self,
        expression: ast.Expression,
        error_message: str,
    ) -> str:
        if isinstance(expression, ast.StringLiteral):
            self._validate_static_string_literal(expression)
            self.expression_types[id(expression)] = ast.TypeName.STRING
            text = decode_static_text(expression.value)
            self.static_text_values[id(expression)] = text
            return text
        if isinstance(expression, ast.Identifier):
            binding = self._lookup_binding(expression.name)
            if binding is not None and binding.static_text is not None:
                self.expression_types[id(expression)] = ast.TypeName.STRING
                self.static_text_values[id(expression)] = binding.static_text
                return binding.static_text
        if (
            isinstance(expression, ast.BinaryExpression)
            and expression.operator is ast.BinaryOperator.ADD
        ):
            left = self._constant_static_text_value(expression.left, error_message)
            right = self._constant_static_text_value(expression.right, error_message)
            self.expression_types[id(expression)] = ast.TypeName.STRING
            text = left + right
            self.static_text_values[id(expression)] = text
            return text
        if isinstance(expression, ast.IndexExpression):
            source = self._constant_static_text_value(expression.target, error_message)
            index_type = self._analyze_expression(expression.index, ast.TypeName.TRYTE)
            self._require_type(
                index_type,
                ast.TypeName.TRYTE,
                expression.index.location,
                "static text index",
            )
            index = self._constant_tryte_value(expression.index)
            if index is None:
                raise SemanticError(
                    "static text index must be a tryte expression known at compile time",
                    expression.index.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            if index < 0:
                raise SemanticError(
                    "static text index must be non-negative",
                    expression.index.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            if index >= len(source):
                raise SemanticError(
                    f"static text index {index} is outside text bounds [0, {len(source)})",
                    expression.index.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            self.expression_types[id(expression)] = ast.TypeName.STRING
            text = source[index]
            self.static_text_values[id(expression)] = text
            return text
        if isinstance(expression, ast.SliceExpression):
            source = self._constant_static_text_value(expression.target, error_message)
            start_type = self._analyze_expression(expression.start, ast.TypeName.TRYTE)
            self._require_type(
                start_type,
                ast.TypeName.TRYTE,
                expression.start.location,
                "static text slice start",
            )
            end_type = self._analyze_expression(expression.end, ast.TypeName.TRYTE)
            self._require_type(
                end_type,
                ast.TypeName.TRYTE,
                expression.end.location,
                "static text slice end",
            )
            start = self._constant_tryte_value(expression.start)
            end = self._constant_tryte_value(expression.end)
            if start is None or end is None:
                raise SemanticError(
                    "static text slice bounds must be tryte expressions known at compile time",
                    expression.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            if start < 0 or end < 0:
                raise SemanticError(
                    "static text slice bounds must be non-negative",
                    expression.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            if start > end:
                raise SemanticError(
                    f"static text slice start {start} exceeds end {end}",
                    expression.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            if end > len(source):
                raise SemanticError(
                    f"static text slice end {end} is outside text bounds [0, {len(source)}]",
                    expression.end.location,
                    diagnostic_code=(
                        DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION
                    ),
                )
            self.expression_types[id(expression)] = ast.TypeName.STRING
            text = source[start:end]
            self.static_text_values[id(expression)] = text
            return text
        if isinstance(expression, ast.CallExpression):
            if (
                expression.simple_function_name is not None
                and expression.function_name in STATIC_TEXT_TRANSFORM_BUILTINS
            ):
                self._analyze_static_text_transform_call(expression)
                text = self.static_text_values.get(id(expression))
                if text is not None:
                    return text
        raise SemanticError(
            error_message,
            expression.location,
            diagnostic_code=DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION,
        )

    def _is_constant_static_text_expression(self, expression: ast.Expression) -> bool:
        if isinstance(expression, ast.StringLiteral):
            return True
        if isinstance(expression, ast.Identifier):
            binding = self._lookup_binding(expression.name)
            return binding is not None and binding.static_text is not None
        if isinstance(expression, ast.IndexExpression):
            return (
                self._is_constant_static_text_expression(expression.target)
                and self._is_constant_tryte_expression(expression.index)
            )
        if isinstance(expression, ast.SliceExpression):
            return (
                self._is_constant_static_text_expression(expression.target)
                and self._is_constant_tryte_expression(expression.start)
                and self._is_constant_tryte_expression(expression.end)
            )
        if isinstance(expression, ast.CallExpression):
            if expression.simple_function_name is None:
                return False
            return self._is_constant_static_text_transform_call(expression)
        return (
            isinstance(expression, ast.BinaryExpression)
            and expression.operator is ast.BinaryOperator.ADD
            and self._is_constant_static_text_expression(expression.left)
            and self._is_constant_static_text_expression(expression.right)
        )

    @staticmethod
    def _reject_string_operation(
        type_name: ast.DeclaredType,
        location: SourceLocation,
        message: str,
    ) -> None:
        if type_name is ast.TypeName.STRING:
            raise SemanticError(
                message,
                location,
                diagnostic_code=DiagnosticCode.SEMANTIC_UNSUPPORTED_STRING_OPERATION,
            )

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
        actual: ast.DeclaredType,
        expected: ast.DeclaredType,
        location: SourceLocation,
        subject: str,
        *,
        diagnostic_code: DiagnosticCode = DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
    ) -> None:
        if not _types_equal(actual, expected):
            raise SemanticError(
                (
                    f"{subject} has type {_type_display(actual)}; "
                    f"expected {_type_display(expected)}"
                ),
                location,
                diagnostic_code=diagnostic_code,
            )


def _types_equal(left: ast.DeclaredType, right: ast.DeclaredType) -> bool:
    if isinstance(left, ast.TypeName) or isinstance(right, ast.TypeName):
        return left is right
    if isinstance(left, ast.NominalType) and isinstance(right, ast.NominalType):
        return left.name == right.name
    if isinstance(left, ast.ArrayType) and isinstance(right, ast.ArrayType):
        return (
            left.length == right.length
            and _types_equal(left.element_type, right.element_type)
        )
    return False


def _type_display(type_name: ast.DeclaredType) -> str:
    if isinstance(type_name, ast.TypeName):
        return type_name.value
    if isinstance(type_name, ast.NominalType):
        return type_name.name
    if isinstance(type_name, ast.ArrayType):
        return f"{_type_display(type_name.element_type)}[{type_name.length}]"
    raise AssertionError(f"unknown declared type {type_name!r}")


def analyze(program: ast.Program) -> SemanticModel:
    return SemanticAnalyzer().analyze(program)
