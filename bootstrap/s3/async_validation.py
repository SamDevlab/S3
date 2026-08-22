"""Fail-closed semantic gates for the M1.81/M1.82 async language surface."""

from __future__ import annotations

from . import ast
from .async_language import ParsedAsyncLanguageSource
from .async_limits import MAX_SELECT_ARITY
from .diagnostics import DiagnosticCode, SemanticError


def validate_async_language_semantics(parsed: ParsedAsyncLanguageSource) -> None:
    """Preserve PR182 borrow/await rules and make Future ownership unambiguous.

    The executable V1 deliberately uses a closed linear subset.  Unsupported
    constructs fail at compile time rather than falling through to the old
    synchronous direct-call path.
    """

    program = parsed.program
    syntax = parsed.syntax
    async_names = syntax.async_function_names
    await_offsets = syntax.await_call_offsets
    future_markers = tuple(item for item in syntax.futures if item.name is not None)
    future_names = {item.name for item in future_markers}

    # The executable lowerer uses a compact name-keyed Future ownership table.
    # Until lexical Future ids become their own AST node, reject shadowing or
    # reuse that could make that table ambiguous across functions.
    for name in sorted(future_names):
        declarations = 0
        for function in program.functions:
            declarations += sum(parameter.name == name for parameter in function.parameters)
            declarations += sum(
                isinstance(statement, ast.VariableDeclaration) and statement.name == name
                for statement in function.body.statements
            )
        marker_count = sum(item.name == name for item in future_markers)
        if declarations != marker_count:
            raise SemanticError(
                f"Future owner name '{name}' is shadowed or reused by a non-Future binding; M1.82 V1 requires globally unambiguous Future owner names",
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )

    for function in program.functions:
        is_async = function.name in async_names
        live_references = {
            parameter.name
            for parameter in function.parameters
            if isinstance(parameter.type_name, (ast.ReferenceType, ast.SliceType))
        }
        function_future_names = {
            parameter.name for parameter in function.parameters if parameter.name in future_names
        }
        function_future_names.update(
            statement.name
            for statement in function.body.statements
            if isinstance(statement, ast.VariableDeclaration) and statement.name in future_names
        )
        _validate_linear_block(
            function.body,
            function_name=function.name,
            function_is_async=is_async,
            async_names=async_names,
            await_offsets=await_offsets,
            future_names=function_future_names,
            live_references=live_references,
        )


def _validate_linear_block(
    block: ast.Block,
    *,
    function_name: str,
    function_is_async: bool,
    async_names: frozenset[str],
    await_offsets: frozenset[int],
    future_names: set[str],
    live_references: set[str],
) -> None:
    references = set(live_references)
    for statement in block.statements:
        if isinstance(statement, ast.VariableDeclaration):
            expression = _single(statement.initializer)
            _validate_expression(
                expression,
                function_name,
                function_is_async,
                async_names,
                await_offsets,
                future_names,
                references,
                allow_unawaited_async=statement.name in future_names,
            )
            if isinstance(statement.type_name, (ast.ReferenceType, ast.SliceType)):
                references.add(statement.name)
        elif isinstance(statement, (ast.AssignmentStatement, ast.CompoundAssignmentStatement)):
            expression = _single(statement.value)
            _validate_expression(
                expression,
                function_name,
                function_is_async,
                async_names,
                await_offsets,
                future_names,
                references,
                allow_unawaited_async=False,
            )
        elif isinstance(statement, (ast.ReturnStatement, ast.DiscardStatement)):
            _validate_expression(
                statement.expression,
                function_name,
                function_is_async,
                async_names,
                await_offsets,
                future_names,
                references,
                allow_unawaited_async=False,
            )
        elif isinstance(statement, ast.SelectStatement):
            if not 1 <= len(statement.arms) <= MAX_SELECT_ARITY:
                raise SemanticError(
                    f"select requires between 1 and {MAX_SELECT_ARITY} arms",
                    statement.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
                )
            for arm in statement.arms:
                _validate_expression(
                    arm.operation,
                    function_name,
                    function_is_async,
                    async_names,
                    await_offsets,
                    future_names,
                    set(references),
                    allow_unawaited_async=False,
                )
                _validate_linear_block(
                    arm.body,
                    function_name=function_name,
                    function_is_async=function_is_async,
                    async_names=async_names,
                    await_offsets=await_offsets,
                    future_names=set(future_names),
                    live_references=set(references),
                )
        elif isinstance(statement, ast.SwitchStatement):
            _validate_expression(statement.expression, function_name, function_is_async, async_names, await_offsets, future_names, references, False)
            for case in statement.cases:
                _validate_linear_block(
                    case.body,
                    function_name=function_name,
                    function_is_async=function_is_async,
                    async_names=async_names,
                    await_offsets=await_offsets,
                    future_names=set(future_names),
                    live_references=set(references),
                )
        elif isinstance(statement, ast.WhileStatement):
            _validate_expression(statement.condition, function_name, function_is_async, async_names, await_offsets, future_names, references, False)
            _validate_linear_block(
                statement.body,
                function_name=function_name,
                function_is_async=function_is_async,
                async_names=async_names,
                await_offsets=await_offsets,
                future_names=set(future_names),
                live_references=set(references),
            )
        elif isinstance(statement, ast.ForStatement):
            for expression in (statement.start_expression, statement.end_expression, statement.step_expression):
                _validate_expression(expression, function_name, function_is_async, async_names, await_offsets, future_names, references, False)
            _validate_linear_block(
                statement.body,
                function_name=function_name,
                function_is_async=function_is_async,
                async_names=async_names,
                await_offsets=await_offsets,
                future_names=set(future_names),
                live_references=set(references),
            )


def _validate_expression(
    expression: ast.Expression,
    function_name: str,
    function_is_async: bool,
    async_names: frozenset[str],
    await_offsets: frozenset[int],
    future_names: set[str],
    live_references: set[str],
    allow_unawaited_async: bool,
) -> None:
    awaited = expression.location.offset in await_offsets
    if awaited:
        if not function_is_async:
            raise SemanticError(
                f"await is only valid inside async fn; '{function_name}' is synchronous",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )
        if live_references:
            raise SemanticError(
                "ordinary lexical reference/slice is live across await: " + ", ".join(sorted(live_references)),
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )
        if isinstance(expression, ast.CallExpression):
            callee = expression.simple_function_name
            if callee not in async_names:
                raise SemanticError(
                    f"await target '{callee}' is not an async function",
                    expression.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
                )
        elif isinstance(expression, ast.Identifier):
            if expression.name not in future_names:
                raise SemanticError(
                    f"await target '{expression.name}' is not an owned Future",
                    expression.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
                )
        else:
            raise SemanticError("await requires a direct async call or owned Future", expression.location)

    if isinstance(expression, ast.CallExpression):
        callee = expression.simple_function_name
        if callee in async_names and not awaited and not allow_unawaited_async:
            raise SemanticError(
                f"call to async function '{callee}' must be awaited or stored in Future<T>",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )
        if function_is_async and callee not in async_names:
            # The current executable IR does not yet carry arbitrary synchronous
            # call frames.  Reject rather than silently execute them through the
            # conventional synchronous pipeline.
            raise SemanticError(
                f"synchronous call '{callee}' inside async fn is deferred until the async IR call-frame adapter is explicit",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )
    for child in _children(expression):
        _validate_expression(
            child,
            function_name,
            function_is_async,
            async_names,
            await_offsets,
            future_names,
            live_references,
            False,
        )


def _single(initializer: ast.Initializer) -> ast.Expression:
    if isinstance(initializer, ast.ArrayLiteral):
        # No await token can bind an ArrayLiteral root. Child expressions are
        # still validated for accidental async calls.
        if not initializer.elements:
            raise SemanticError("empty array initializer is invalid")
        return initializer.elements[0]
    return initializer


def _children(expression: ast.Expression) -> tuple[ast.Expression, ...]:
    if isinstance(expression, ast.CallExpression):
        return tuple(argument.expression for argument in expression.arguments)
    if isinstance(expression, ast.RecordExpression):
        return tuple(field.expression for field in expression.fields)
    if isinstance(expression, ast.GenericTypeExpression):
        return (expression.target,)
    if isinstance(expression, ast.IndexExpression):
        return (expression.target, expression.index)
    if isinstance(expression, ast.SliceExpression):
        return (expression.target, expression.start, expression.end)
    if isinstance(expression, ast.FieldAccessExpression):
        return (expression.target,)
    if isinstance(expression, (ast.AddressOfExpression, ast.DereferenceExpression, ast.UnaryExpression)):
        return (expression.operand,)
    if isinstance(expression, ast.BinaryExpression):
        return (expression.left, expression.right)
    if isinstance(expression, ast.MatchExpression):
        return (expression.selector, *(case.expression for case in expression.cases))
    if isinstance(expression, ast.LenExpression):
        return (expression.argument,)
    return ()
