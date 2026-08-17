"""Closed, explicit generic-function specialization for M1.53."""

from __future__ import annotations

from dataclasses import replace

from . import ast
from .diagnostics import DiagnosticCode, SemanticError


_SCALAR_TYPES = {
    ast.TypeName.TRIT,
    ast.TypeName.TRYTE,
    ast.TypeName.I64,
    ast.TypeName.F64,
    ast.TypeName.STRING,
}
_OWNED_TYPES = {
    ast.TypeName.BYTES,
    ast.TypeName.TEXT,
    ast.TypeName.TRYTE_VECTOR,
    ast.TypeName.I64_VECTOR,
    ast.TypeName.F64_VECTOR,
    ast.TypeName.I64_MAP,
    ast.TypeName.I64_SET,
}


def _type_key(type_name: ast.DeclaredType) -> str:
    if isinstance(type_name, ast.TypeName):
        return type_name.value
    if isinstance(type_name, ast.TypeParameterType):
        return type_name.name
    if isinstance(type_name, ast.NominalType):
        return type_name.name
    if isinstance(type_name, ast.ArrayType):
        return f"{_type_key(type_name.element_type)}_array{type_name.length}"
    if isinstance(type_name, ast.ReferenceType):
        return f"ref_{'mut' if type_name.mutable else 'shared'}_{_type_key(type_name.target)}"
    if isinstance(type_name, ast.SliceType):
        return f"slice_{'mut' if type_name.mutable else 'shared'}_{type_name.element_type.value}"
    raise TypeError(f"unsupported generic type argument {type_name!r}")


def _substitute_type(
    type_name: ast.DeclaredType,
    substitutions: dict[str, ast.DeclaredType],
) -> ast.DeclaredType:
    if isinstance(type_name, ast.TypeParameterType):
        try:
            return substitutions[type_name.name]
        except KeyError as error:
            raise SemanticError(
                f"unresolved type parameter '{type_name.name}'",
                type_name.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            ) from error
    if isinstance(type_name, ast.ArrayType):
        return replace(
            type_name,
            element_type=_substitute_type(type_name.element_type, substitutions),
        )
    if isinstance(type_name, ast.ReferenceType):
        return replace(
            type_name,
            target=_substitute_type(type_name.target, substitutions),
        )
    return type_name


def _validate_constraint(
    parameter: ast.TypeParameter,
    argument: ast.DeclaredType,
    location,
) -> None:
    if isinstance(argument, (ast.ArrayType, ast.NominalType, ast.ReferenceType, ast.SliceType)):
        raise SemanticError(
            f"generic type parameter '{parameter.name}' accepts only closed scalar or owned leaves",
            argument.location,
            diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
        )
    allowed = (
        _SCALAR_TYPES
        if parameter.constraint == "scalar"
        else _OWNED_TYPES
        if parameter.constraint == "owned"
        else _SCALAR_TYPES | _OWNED_TYPES
    )
    if parameter.constraint not in {"scalar", "owned", "value"}:
        raise SemanticError(
            f"unknown generic constraint '{parameter.constraint}'",
            parameter.location,
            diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        )
    if argument not in allowed:
        raise SemanticError(
            f"type argument '{_type_key(argument)}' does not satisfy {parameter.constraint} constraint",
            getattr(argument, "location", location),
            diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
        )


def _expression(
    expression: ast.Expression,
    substitutions: dict[str, ast.DeclaredType],
    specialize,
) -> ast.Expression:
    if isinstance(expression, ast.CallExpression):
        callee = expression.callee
        arguments = tuple(
            replace(argument, expression=_expression(argument.expression, substitutions, specialize))
            for argument in expression.arguments
        )
        type_arguments = tuple(
            _substitute_type(argument, substitutions)
            for argument in expression.type_arguments
        )
        if isinstance(callee, ast.Identifier) and callee.name in specialize.generic_names:
            if not type_arguments:
                raise SemanticError(
                    f"generic function '{callee.name}' requires explicit type arguments",
                    expression.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                )
            name = specialize(callee.name, type_arguments, expression.location)
            callee = replace(callee, name=name)
            type_arguments = ()
        return replace(
            expression,
            callee=callee,
            arguments=arguments,
            type_arguments=type_arguments,
        )
    if isinstance(expression, ast.RecordExpression):
        return replace(
            expression,
            fields=tuple(
                replace(field, expression=_expression(field.expression, substitutions, specialize))
                for field in expression.fields
            ),
        )
    if isinstance(expression, ast.IndexExpression):
        return replace(
            expression,
            target=_expression(expression.target, substitutions, specialize),
            index=_expression(expression.index, substitutions, specialize),
        )
    if isinstance(expression, ast.SliceExpression):
        return replace(
            expression,
            target=_expression(expression.target, substitutions, specialize),
            start=_expression(expression.start, substitutions, specialize),
            end=_expression(expression.end, substitutions, specialize),
        )
    if isinstance(expression, ast.FieldAccessExpression):
        return replace(expression, target=_expression(expression.target, substitutions, specialize))
    if isinstance(expression, ast.AddressOfExpression):
        return replace(expression, operand=_expression(expression.operand, substitutions, specialize))
    if isinstance(expression, ast.DereferenceExpression):
        return replace(expression, operand=_expression(expression.operand, substitutions, specialize))
    if isinstance(expression, ast.UnaryExpression):
        return replace(expression, operand=_expression(expression.operand, substitutions, specialize))
    if isinstance(expression, ast.BinaryExpression):
        return replace(
            expression,
            left=_expression(expression.left, substitutions, specialize),
            right=_expression(expression.right, substitutions, specialize),
        )
    if isinstance(expression, ast.MatchExpression):
        return replace(
            expression,
            selector=_expression(expression.selector, substitutions, specialize),
            cases=tuple(
                replace(case, expression=_expression(case.expression, substitutions, specialize))
                for case in expression.cases
            ),
        )
    if isinstance(expression, ast.LenExpression):
        return replace(expression, argument=_expression(expression.argument, substitutions, specialize))
    return expression


def _initializer(initializer, substitutions, specialize):
    if isinstance(initializer, ast.ArrayLiteral):
        return replace(
            initializer,
            elements=tuple(_expression(item, substitutions, specialize) for item in initializer.elements),
        )
    return _expression(initializer, substitutions, specialize)


def _target(target: ast.AssignmentTarget, substitutions, specialize):
    if isinstance(target, ast.IndexTarget):
        return replace(target, index=_expression(target.index, substitutions, specialize))
    if isinstance(target, ast.DereferenceTarget):
        return replace(target, reference=_expression(target.reference, substitutions, specialize))
    if isinstance(target, ast.FieldTarget):
        return replace(target, target=_expression(target.target, substitutions, specialize))
    return target


def _block(block: ast.Block, substitutions, specialize) -> ast.Block:
    return replace(
        block,
        statements=tuple(_statement(item, substitutions, specialize) for item in block.statements),
    )


def _statement(statement: ast.Statement, substitutions, specialize):
    if isinstance(statement, ast.VariableDeclaration):
        return replace(
            statement,
            type_name=_substitute_type(statement.type_name, substitutions),
            initializer=_initializer(statement.initializer, substitutions, specialize),
        )
    if isinstance(statement, ast.AssignmentStatement):
        return replace(
            statement,
            target=_target(statement.target, substitutions, specialize),
            value=_initializer(statement.value, substitutions, specialize),
        )
    if isinstance(statement, ast.CompoundAssignmentStatement):
        return replace(
            statement,
            target=_target(statement.target, substitutions, specialize),
            value=_initializer(statement.value, substitutions, specialize),
        )
    if isinstance(statement, ast.DiscardStatement):
        return replace(statement, expression=_expression(statement.expression, substitutions, specialize))
    if isinstance(statement, ast.ReturnStatement):
        return replace(statement, expression=_expression(statement.expression, substitutions, specialize))
    if isinstance(statement, ast.SwitchStatement):
        return replace(
            statement,
            expression=_expression(statement.expression, substitutions, specialize),
            cases=tuple(
                replace(case, body=_block(case.body, substitutions, specialize))
                for case in statement.cases
            ),
        )
    if isinstance(statement, ast.WhileStatement):
        return replace(
            statement,
            condition=_expression(statement.condition, substitutions, specialize),
            body=_block(statement.body, substitutions, specialize),
        )
    if isinstance(statement, ast.ForStatement):
        return replace(
            statement,
            start_expression=_expression(statement.start_expression, substitutions, specialize),
            end_expression=_expression(statement.end_expression, substitutions, specialize),
            step_expression=_expression(statement.step_expression, substitutions, specialize),
            body=_block(statement.body, substitutions, specialize),
        )
    return statement


def specialize_generic_functions(program: ast.Program) -> ast.Program:
    generic = {
        function.name: function
        for function in program.functions
        if function.signature.type_parameters
    }
    if not generic:
        return program

    specialized: dict[tuple[str, tuple[str, ...]], ast.FunctionDeclaration] = {}
    building: set[tuple[str, tuple[str, ...]]] = set()

    class Specializer:
        generic_names = frozenset(generic)

        def __call__(self, name: str, arguments: tuple[ast.DeclaredType, ...], location):
            function = generic[name]
            parameters = function.signature.type_parameters
            if len(arguments) != len(parameters):
                raise SemanticError(
                    f"generic function '{name}' expects {len(parameters)} type argument(s), got {len(arguments)}",
                    location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                )
            substitutions = dict(zip((item.name for item in parameters), arguments, strict=True))
            for parameter, argument in zip(parameters, arguments, strict=True):
                _validate_constraint(parameter, argument, location)
            key = (name, tuple(_type_key(argument) for argument in arguments))
            specialized_name = "__s3_generic__" + name + "__" + "__".join(key[1])
            if key in specialized:
                return specialized_name
            if key in building:
                return specialized_name
            building.add(key)
            signature = replace(
                function.signature,
                name=specialized_name,
                type_parameters=(),
                parameters=tuple(
                    replace(
                        parameter,
                        type_name=_substitute_type(parameter.type_name, substitutions),
                    )
                    for parameter in function.parameters
                ),
                return_type=_substitute_type(function.return_type, substitutions),
            )
            clone = ast.FunctionDeclaration(
                signature,
                _block(function.body, substitutions, self),
                function.location,
                function.exported,
            )
            specialized[key] = clone
            building.remove(key)
            return specialized_name

    specializer = Specializer()
    rewritten: list[ast.FunctionDeclaration] = []
    for function in program.functions:
        if function.signature.type_parameters:
            continue
        rewritten.append(
            replace(
                function,
                body=_block(function.body, {}, specializer),
            )
        )
    rewritten.extend(specialized.values())
    return replace(program, functions=tuple(rewritten))
