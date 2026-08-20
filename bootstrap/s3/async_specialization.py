"""Deterministic closed specialization for compiler-owned async functions."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

from .async_language import AsyncAction, AsyncExecutableFunction, AsyncExecutableProgram, AsyncExpression
from .diagnostics import DiagnosticCode, SemanticError


_SCALAR = frozenset({"trit", "tryte", "i64", "f64", "string"})
_OWNED = frozenset({"bytes", "text", "tryte_vector", "i64_vector", "f64_vector", "i64_map", "i64_set"})


def specialize_async_executable(program: AsyncExecutableProgram) -> AsyncExecutableProgram:
    """Create one deterministic executable/frame identity per async type tuple.

    Generic templates are compiler inputs, not runtime functions. Every direct
    generic async call must carry closed explicit type arguments. Nested calls
    substitute the outer type-parameter names before selecting their own
    specialization.  This mirrors the existing core generic specialization
    model without introducing runtime type erasure.
    """

    templates = {function.name: function for function in program.functions}
    generic_names = {name for name, function in templates.items() if function.generic_parameters}
    if not generic_names:
        return program

    specialized: dict[tuple[str, tuple[str, ...]], AsyncExecutableFunction] = {}

    def request(name: str, arguments: tuple[str, ...]) -> str:
        template = templates.get(name)
        if template is None:
            return name
        if not template.generic_parameters:
            if arguments:
                raise SemanticError(
                    f"non-generic async function '{name}' received type arguments",
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
                )
            return name
        _validate_arguments(template, arguments)
        key = (name, arguments)
        existing = specialized.get(key)
        if existing is not None:
            return existing.name
        specialization_name = _specialization_name(name, arguments)
        substitutions = {
            parameter_name: argument
            for (parameter_name, _constraint), argument in zip(template.generic_parameters, arguments)
        }
        # Reserve the identity before recursively rewriting its body.  Recursive
        # generic calls to the exact same closed tuple therefore terminate.
        placeholder = replace(template, name=specialization_name, generic_parameters=())
        specialized[key] = placeholder
        rewritten_actions = tuple(_rewrite_action(action, substitutions, request) for action in template.actions)
        specialized[key] = replace(placeholder, actions=rewritten_actions)
        return specialization_name

    runtime_functions: list[AsyncExecutableFunction] = []
    for function in program.functions:
        if function.generic_parameters:
            continue
        runtime_functions.append(
            replace(
                function,
                actions=tuple(_rewrite_action(action, {}, request) for action in function.actions),
            )
        )

    # Requests discovered while rewriting non-generic roots recursively populate
    # `specialized`. Sort by executable identity for byte-stable IR order.
    runtime_functions.extend(sorted(specialized.values(), key=lambda item: item.name))
    return AsyncExecutableProgram(tuple(runtime_functions), entry=program.entry)


def _rewrite_action(
    action: AsyncAction,
    substitutions: dict[str, str],
    request,
) -> AsyncAction:
    type_arguments = tuple(substitutions.get(item, item) for item in action.type_arguments)
    callee = action.callee
    if callee is not None:
        callee = request(callee, type_arguments)
        type_arguments = ()
    expression = None if action.expression is None else _rewrite_expression(action.expression, substitutions, request)
    arguments = tuple(_rewrite_expression(item, substitutions, request) for item in action.arguments)
    return replace(action, callee=callee, type_arguments=type_arguments, expression=expression, arguments=arguments)


def _rewrite_expression(expression: AsyncExpression, substitutions: dict[str, str], request) -> AsyncExpression:
    type_arguments = tuple(substitutions.get(item, item) for item in expression.type_arguments)
    name = expression.name
    if name is not None and expression.type_arguments:
        name = request(name, type_arguments)
        type_arguments = ()
    arguments = tuple(_rewrite_expression(item, substitutions, request) for item in expression.arguments)
    return replace(expression, name=name, type_arguments=type_arguments, arguments=arguments)


def _validate_arguments(function: AsyncExecutableFunction, arguments: tuple[str, ...]) -> None:
    if len(arguments) != len(function.generic_parameters):
        raise SemanticError(
            f"generic async function '{function.source_name}' requires {len(function.generic_parameters)} explicit type arguments",
            diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
        )
    for (parameter, constraint), argument in zip(function.generic_parameters, arguments):
        if argument in _SCALAR:
            domain = "scalar"
        elif argument in _OWNED:
            domain = "owned"
        else:
            raise SemanticError(
                f"generic async type argument '{argument}' is not a closed scalar/owned leaf",
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
            )
        valid = constraint == "value" or constraint == domain
        if constraint not in {"scalar", "owned", "value"}:
            raise SemanticError(
                f"unknown generic async constraint '{constraint}' for '{parameter}'",
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )
        if not valid:
            raise SemanticError(
                f"type argument '{argument}' does not satisfy {constraint} constraint for '{parameter}'",
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE,
            )


def _specialization_name(name: str, arguments: tuple[str, ...]) -> str:
    identity = name + "<" + ",".join(arguments) + ">"
    suffix = sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"{name}__async_spec_{suffix}"
