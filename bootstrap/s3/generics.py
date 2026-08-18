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
_VECTOR_ELEMENT_TYPES = {
    ast.TypeName.TRYTE: "tryte",
    ast.TypeName.I64: "i64",
    ast.TypeName.F64: "f64",
}
_GENERIC_MAP_TYPES = {
    (ast.TypeName.I64, ast.TypeName.I64): ast.TypeName.I64_MAP,
}
_GENERIC_SET_TYPES = {
    (ast.TypeName.I64,): ast.TypeName.I64_SET,
}
_GENERIC_VECTOR_BUILTINS = frozenset(
    {
        "vector_new",
        "vector_len",
        "vector_capacity",
        "vector_reserve",
        "vector_push",
        "vector_pop",
        "vector_get",
        "vector_set",
        "vector_clone",
        "vector_slice",
    }
)
_GENERIC_MAP_BUILTINS = frozenset(
    {
        "map_new",
        "map_len",
        "map_capacity",
        "map_reserve",
        "map_put",
        "map_contains",
        "map_get",
        "map_remove",
        "map_key_at",
        "map_value_at",
        "map_clone",
    }
)
_GENERIC_SET_BUILTINS = frozenset(
    {
        "set_new",
        "set_len",
        "set_capacity",
        "set_reserve",
        "set_add",
        "set_contains",
        "set_remove",
        "set_at",
        "set_clone",
    }
)
_GENERIC_COLLECTION_BUILTINS = (
    _GENERIC_VECTOR_BUILTINS | _GENERIC_MAP_BUILTINS | _GENERIC_SET_BUILTINS
)


def _type_key(type_name: ast.DeclaredType) -> str:
    if isinstance(type_name, ast.TypeName):
        return type_name.value
    if isinstance(type_name, ast.TypeParameterType):
        return type_name.name
    if isinstance(type_name, ast.NominalType):
        if type_name.type_arguments:
            return f"{type_name.name}__" + "__".join(
                _type_key(argument) for argument in type_name.type_arguments
            )
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
    if isinstance(type_name, ast.NominalType):
        return replace(
            type_name,
            type_arguments=tuple(
                _substitute_type(argument, substitutions)
                for argument in type_name.type_arguments
            ),
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


def _rewrite_type(
    type_name: ast.DeclaredType,
    substitutions: dict[str, ast.DeclaredType],
    specialize_type,
    location,
) -> ast.DeclaredType:
    type_name = _substitute_type(type_name, substitutions)
    if isinstance(type_name, ast.ArrayType):
        return replace(
            type_name,
            element_type=_rewrite_type(
                type_name.element_type,
                substitutions,
                specialize_type,
                location,
            ),
        )
    if isinstance(type_name, ast.ReferenceType):
        return replace(
            type_name,
            target=_rewrite_type(
                type_name.target,
                substitutions,
                specialize_type,
                location,
            ),
        )
    if isinstance(type_name, ast.NominalType):
        arguments = tuple(
            _rewrite_type(argument, substitutions, specialize_type, location)
            for argument in type_name.type_arguments
        )
        if arguments:
            specialized_name = specialize_type(
                type_name.name,
                arguments,
                type_name.location,
            )
            if isinstance(specialized_name, ast.TypeName):
                return specialized_name
            return ast.NominalType(specialized_name, type_name.location)
        return replace(type_name, type_arguments=())
    return type_name


def _label(label, substitutions, specialize):
    if isinstance(label, ast.FieldAccessExpression):
        return replace(
            label,
            target=_expression(label.target, substitutions, specialize),
        )
    if isinstance(label, ast.MatchPayloadLabel):
        return replace(
            label,
            variant=replace(
                label.variant,
                target=_expression(label.variant.target, substitutions, specialize),
            ),
        )
    return label


def _expression(
    expression: ast.Expression,
    substitutions: dict[str, ast.DeclaredType],
    specialize,
) -> ast.Expression:
    if isinstance(expression, ast.CallExpression):
        callee = _expression(expression.callee, substitutions, specialize)
        arguments = tuple(
            replace(argument, expression=_expression(argument.expression, substitutions, specialize))
            for argument in expression.arguments
        )
        type_arguments = tuple(
            specialize.rewrite_type(
                _substitute_type(argument, substitutions),
                expression.location,
            )
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
        elif isinstance(callee, ast.Identifier) and callee.name in specialize.generic_builtin_names:
            if not type_arguments:
                raise SemanticError(
                    f"generic builtin '{callee.name}' requires explicit type arguments",
                    expression.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                )
            name = specialize.generic_builtin(callee.name, type_arguments, expression.location)
            callee = replace(callee, name=name)
            type_arguments = ()
        return replace(
            expression,
            callee=callee,
            arguments=arguments,
            type_arguments=type_arguments,
        )
    if isinstance(expression, ast.GenericTypeExpression):
        target = _expression(expression.target, substitutions, specialize)
        if not isinstance(target, ast.Identifier):
            raise SemanticError(
                "generic type qualifier must name a declared type",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )
        type_arguments = tuple(
            specialize.rewrite_type(
                _substitute_type(argument, substitutions),
                expression.location,
            )
            for argument in expression.type_arguments
        )
        return replace(
            target,
            name=specialize.type_name(target.name, type_arguments, expression.location),
        )
    if isinstance(expression, ast.RecordExpression):
        type_arguments = tuple(
            specialize.rewrite_type(
                _substitute_type(argument, substitutions),
                expression.location,
            )
            for argument in expression.type_arguments
        )
        record_name = expression.type_name
        if type_arguments:
            base, separator, suffix = record_name.partition(".")
            record_name = specialize.type_name(base, type_arguments, expression.location)
            if separator:
                record_name += separator + suffix
        return replace(
            expression,
            type_name=record_name,
            type_arguments=(),
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
                replace(
                    case,
                    label=_label(case.label, substitutions, specialize),
                    expression=_expression(case.expression, substitutions, specialize),
                )
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
            type_name=specialize.rewrite_type(
                _substitute_type(statement.type_name, substitutions),
                statement.location,
            ),
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
                replace(
                    case,
                    label=_label(case.label, substitutions, specialize),
                    body=_block(case.body, substitutions, specialize),
                )
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
    generic_functions = {
        function.name: function
        for function in program.functions
        if function.signature.type_parameters
    }
    generic_records = {
        record.name: record
        for record in program.records
        if record.type_parameters
    }
    generic_enums = {
        enum.name: enum
        for enum in program.enums
        if enum.type_parameters
    }
    generic_types = {**generic_records, **generic_enums}

    specialized_records: dict[tuple[str, tuple[str, ...]], ast.RecordDeclaration] = {}
    specialized_enums: dict[tuple[str, tuple[str, ...]], ast.EnumDeclaration] = {}
    building_types: set[tuple[str, tuple[str, ...]]] = set()

    class TypeSpecializer:
        generic_names = frozenset(generic_types)

        def rewrite_type(self, type_name: ast.DeclaredType, location):
            return _rewrite_type(type_name, {}, self, location)

        def type_name(
            self,
            name: str,
            arguments: tuple[ast.DeclaredType, ...],
            location,
        ) -> str:
            if name == "vector":
                if len(arguments) != 1:
                    raise SemanticError(
                        f"generic type 'vector' expects one type argument, got {len(arguments)}",
                        location,
                        diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                    )
                element = arguments[0]
                if element not in _VECTOR_ELEMENT_TYPES:
                    raise SemanticError(
                        "vector<T> accepts only tryte, i64, or f64 elements",
                        location,
                        diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                    )
                return {
                    ast.TypeName.TRYTE: ast.TypeName.TRYTE_VECTOR,
                    ast.TypeName.I64: ast.TypeName.I64_VECTOR,
                    ast.TypeName.F64: ast.TypeName.F64_VECTOR,
                }[element]
            if name in {"map", "set"}:
                supported = (
                    _GENERIC_MAP_TYPES if name == "map" else _GENERIC_SET_TYPES
                )
                try:
                    return supported[arguments]
                except KeyError as error:
                    expected = "map<i64, i64>" if name == "map" else "set<i64>"
                    raise SemanticError(
                        f"generic type '{name}' currently supports only {expected}",
                        location,
                        diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                    ) from error
            declaration = generic_types.get(name)
            if declaration is None:
                raise SemanticError(
                    f"type '{name}' does not accept type arguments",
                    location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                )
            parameters = declaration.type_parameters
            if len(arguments) != len(parameters):
                raise SemanticError(
                    f"generic type '{name}' expects {len(parameters)} type argument(s), got {len(arguments)}",
                    location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                )
            for parameter, argument in zip(parameters, arguments, strict=True):
                _validate_constraint(parameter, argument, location)
            key = (name, tuple(_type_key(argument) for argument in arguments))
            specialized_name = "__s3_generic_type__" + name + "__" + "__".join(key[1])
            if key in specialized_records or key in specialized_enums:
                return specialized_name
            if key in building_types:
                return specialized_name
            building_types.add(key)
            substitutions = dict(
                zip((item.name for item in parameters), arguments, strict=True)
            )
            if isinstance(declaration, ast.RecordDeclaration):
                clone = replace(
                    declaration,
                    name=specialized_name,
                    type_parameters=(),
                    fields=tuple(
                        replace(
                            field,
                            type_name=_rewrite_type(
                                field.type_name,
                                substitutions,
                                self,
                                field.location,
                            ),
                        )
                        for field in declaration.fields
                    ),
                )
                specialized_records[key] = clone
            else:
                clone = replace(
                    declaration,
                    name=specialized_name,
                    type_parameters=(),
                    variants=tuple(
                        replace(
                            variant,
                            payload_fields=tuple(
                                replace(
                                    field,
                                    type_name=_rewrite_type(
                                        field.type_name,
                                        substitutions,
                                        self,
                                        field.location,
                                    ),
                                )
                                for field in variant.payload_fields
                            ),
                        )
                        for variant in declaration.variants
                    ),
                )
                specialized_enums[key] = clone
            building_types.remove(key)
            return specialized_name

        __call__ = type_name

    type_specializer = TypeSpecializer()

    specialized_functions: dict[tuple[str, tuple[str, ...]], ast.FunctionDeclaration] = {}
    building_functions: set[tuple[str, tuple[str, ...]]] = set()

    class Specializer:
        generic_names = frozenset(generic_functions)
        generic_builtin_names = _GENERIC_COLLECTION_BUILTINS

        def rewrite_type(self, type_name: ast.DeclaredType, location):
            return type_specializer.rewrite_type(type_name, location)

        def type_name(self, name: str, arguments, location):
            return type_specializer.type_name(name, arguments, location)

        def generic_builtin(self, name: str, arguments, location):
            if name in _GENERIC_VECTOR_BUILTINS:
                if len(arguments) != 1 or arguments[0] not in _VECTOR_ELEMENT_TYPES:
                    raise SemanticError(
                        f"generic builtin '{name}' requires one of tryte, i64, or f64 as its type argument",
                        location,
                        diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                    )
                return _VECTOR_ELEMENT_TYPES[arguments[0]] + "_" + name
            if name in _GENERIC_MAP_BUILTINS:
                if tuple(arguments) != (ast.TypeName.I64, ast.TypeName.I64):
                    raise SemanticError(
                        f"generic builtin '{name}' requires map<i64, i64> type arguments",
                        location,
                        diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                    )
                return "i64_" + name
            if name in _GENERIC_SET_BUILTINS:
                if tuple(arguments) != (ast.TypeName.I64,):
                    raise SemanticError(
                        f"generic builtin '{name}' requires set<i64> type arguments",
                        location,
                        diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                    )
                return "i64_" + name
            else:
                raise SemanticError(
                    f"unknown generic builtin '{name}'",
                    location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                )

        def __call__(self, name: str, arguments: tuple[ast.DeclaredType, ...], location):
            function = generic_functions[name]
            parameters = function.signature.type_parameters
            if len(arguments) != len(parameters):
                raise SemanticError(
                    f"generic function '{name}' expects {len(parameters)} type argument(s), got {len(arguments)}",
                    location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                )
            arguments = tuple(
                type_specializer.rewrite_type(argument, location)
                for argument in arguments
            )
            substitutions = dict(zip((item.name for item in parameters), arguments, strict=True))
            for parameter, argument in zip(parameters, arguments, strict=True):
                _validate_constraint(parameter, argument, location)
            key = (name, tuple(_type_key(argument) for argument in arguments))
            specialized_name = "__s3_generic__" + name + "__" + "__".join(key[1])
            if key in specialized_functions:
                return specialized_name
            if key in building_functions:
                return specialized_name
            building_functions.add(key)
            signature = replace(
                function.signature,
                name=specialized_name,
                type_parameters=(),
                parameters=tuple(
                    replace(
                        parameter,
                        type_name=_rewrite_type(
                            parameter.type_name,
                            substitutions,
                            type_specializer,
                            parameter.location,
                        ),
                    )
                    for parameter in function.parameters
                ),
                return_type=_rewrite_type(
                    function.return_type,
                    substitutions,
                    type_specializer,
                    function.location,
                ),
            )
            clone = ast.FunctionDeclaration(
                signature,
                _block(function.body, substitutions, self),
                function.location,
                function.exported,
            )
            specialized_functions[key] = clone
            building_functions.remove(key)
            return specialized_name

    specializer = Specializer()

    rewritten_records = [
        replace(
            record,
            fields=tuple(
                replace(
                    field,
                    type_name=type_specializer.rewrite_type(field.type_name, field.location),
                )
                for field in record.fields
            ),
        )
        for record in program.records
        if not record.type_parameters
    ]
    rewritten_enums = [
        replace(
            enum,
            variants=tuple(
                replace(
                    variant,
                    payload_fields=tuple(
                        replace(
                            field,
                            type_name=type_specializer.rewrite_type(
                                field.type_name,
                                field.location,
                            ),
                        )
                        for field in variant.payload_fields
                    ),
                )
                for variant in enum.variants
            ),
        )
        for enum in program.enums
        if not enum.type_parameters
    ]
    rewritten: list[ast.FunctionDeclaration] = []
    for function in program.functions:
        if function.signature.type_parameters:
            continue
        signature = replace(
            function.signature,
            parameters=tuple(
                replace(
                    parameter,
                    type_name=type_specializer.rewrite_type(
                        parameter.type_name,
                        parameter.location,
                    ),
                )
                for parameter in function.parameters
            ),
            return_type=type_specializer.rewrite_type(
                function.return_type,
                function.location,
            ),
        )
        rewritten.append(
            replace(
                function,
                signature=signature,
                body=_block(function.body, {}, specializer),
            )
        )
    rewritten.extend(specialized_functions.values())
    rewritten_foreign = tuple(
        replace(
            foreign,
            signature=replace(
                foreign.signature,
                parameters=tuple(
                    replace(
                        parameter,
                        type_name=type_specializer.rewrite_type(
                            parameter.type_name,
                            parameter.location,
                        ),
                    )
                    for parameter in foreign.signature.parameters
                ),
                return_type=type_specializer.rewrite_type(
                    foreign.signature.return_type,
                    foreign.location,
                ),
            ),
        )
        for foreign in program.foreign_functions
    )
    return replace(
        program,
        functions=tuple(rewritten),
        records=tuple(rewritten_records) + tuple(specialized_records.values()),
        enums=tuple(rewritten_enums) + tuple(specialized_enums.values()),
        foreign_functions=rewritten_foreign,
    )
