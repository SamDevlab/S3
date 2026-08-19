"""First-class bounded async syntax front-end and suspension-plan lowering for M1.71.

The existing recursive-descent parser remains the core S3 grammar parser. This
module recognizes the two contextual M1.71 keywords, ``async`` and ``await``,
replaces only those keyword spans with whitespace so source offsets remain
stable, delegates the remainder to the core parser, validates async-specific
semantics, and produces a deterministic compiler suspension plan.

M1.71 deliberately keeps Future values implicit: an async function call must be
immediately awaited. This avoids introducing a general Future type, shared
ownership, or borrow lifetimes in V1 while still making ``async fn`` / ``await``
source-visible and compiler-checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from . import ast
from .diagnostics import DiagnosticCode, ParseError, SemanticError, SourceLocation
from .lexer import SyntaxMode, Token, TokenKind, tokenize
from .parser import parse_tokens


@dataclass(frozen=True, slots=True)
class AsyncFunctionSyntax:
    name: str
    keyword_location: SourceLocation
    function_location: SourceLocation


@dataclass(frozen=True, slots=True)
class AwaitSyntax:
    keyword_location: SourceLocation
    call_location: SourceLocation
    callee: str


@dataclass(frozen=True, slots=True)
class AsyncSyntaxTree:
    """Async-specific syntax side tree keyed by source-stable locations."""

    functions: tuple[AsyncFunctionSyntax, ...] = ()
    awaits: tuple[AwaitSyntax, ...] = ()
    source_sha256: str = ""

    @property
    def async_function_names(self) -> frozenset[str]:
        return frozenset(item.name for item in self.functions)

    @property
    def await_call_offsets(self) -> frozenset[int]:
        return frozenset(item.call_location.offset for item in self.awaits)


@dataclass(frozen=True, slots=True)
class ParsedAsyncSource:
    tokens: tuple[Token, ...]
    program: ast.Program
    syntax: AsyncSyntaxTree


@dataclass(frozen=True, slots=True)
class AsyncSuspensionPoint:
    index: int
    call_offset: int
    callee: str
    suspended_state: str
    resume_state: str


@dataclass(frozen=True, slots=True)
class AsyncStateMachinePlan:
    """Deterministic compiler lowering plan for one source-level async function."""

    function_name: str
    frame_slots: tuple[str, ...]
    suspension_points: tuple[AsyncSuspensionPoint, ...]
    states: tuple[str, ...]
    lowering_model: str = "compiler_state_machine_plan_with_hosted_direct_call_execution"


def parse_async_source(
    source: str,
    *,
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> ParsedAsyncSource:
    """Parse S3 source including contextual ``async fn`` and ``await call()``."""

    if mode is not SyntaxMode.V0_6:
        if "async" in source or "await" in source:
            raise ParseError(
                "async/await requires source syntax 0.6",
                SourceLocation(0, 1, 1),
            )
        tokens = tokenize(source, mode=mode)
        return ParsedAsyncSource(
            tokens,
            parse_tokens(tokens, mode=mode),
            AsyncSyntaxTree(source_sha256=sha256(source.encode("utf-8")).hexdigest()),
        )

    original_tokens = tokenize(source, mode=mode)
    replacements: list[tuple[int, int]] = []
    async_functions: list[AsyncFunctionSyntax] = []
    awaits: list[AwaitSyntax] = []

    for index, token in enumerate(original_tokens):
        if token.kind is not TokenKind.IDENTIFIER:
            continue
        if token.text == "async":
            next_token = _token_at(original_tokens, index + 1)
            name_token = _token_at(original_tokens, index + 2)
            if next_token.kind is not TokenKind.FN or name_token.kind is not TokenKind.IDENTIFIER:
                raise ParseError(
                    "'async' is reserved for 'async fn' in M1.71",
                    token.location,
                )
            async_functions.append(
                AsyncFunctionSyntax(
                    name_token.text,
                    token.location,
                    next_token.location,
                )
            )
            replacements.append((token.position, len(token.text)))
            continue
        if token.text == "await":
            callee = _token_at(original_tokens, index + 1)
            open_paren = _token_at(original_tokens, index + 2)
            if callee.kind is not TokenKind.IDENTIFIER or open_paren.kind is not TokenKind.LEFT_PAREN:
                raise ParseError(
                    "M1.71 await requires a direct function call",
                    token.location,
                )
            awaits.append(AwaitSyntax(token.location, callee.location, callee.text))
            replacements.append((token.position, len(token.text)))

    transformed = _replace_with_spaces(source, replacements)
    transformed_tokens = tokenize(transformed, mode=mode)
    program = parse_tokens(transformed_tokens, mode=mode)
    syntax = AsyncSyntaxTree(
        tuple(async_functions),
        tuple(awaits),
        sha256(source.encode("utf-8")).hexdigest(),
    )
    _validate_syntax_bindings(program, syntax)
    return ParsedAsyncSource(original_tokens, program, syntax)


def validate_async_semantics(program: ast.Program, syntax: AsyncSyntaxTree) -> None:
    """Validate the fail-closed M1.71 source semantics before core type analysis."""

    async_names = syntax.async_function_names
    awaited = {item.call_location.offset: item for item in syntax.awaits}
    observed_awaits: set[int] = set()
    functions = {function.name: function for function in program.functions}

    for name in async_names:
        function = functions[name]
        if function.signature.type_parameters:
            raise SemanticError(
                "generic async functions are deferred beyond M1.71 V1",
                function.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )

    for function in program.functions:
        live_references = {
            parameter.name
            for parameter in function.parameters
            if isinstance(parameter.type_name, (ast.ReferenceType, ast.SliceType))
        }
        _validate_block(
            function.body,
            function_name=function.name,
            function_is_async=function.name in async_names,
            async_names=async_names,
            awaited=awaited,
            observed_awaits=observed_awaits,
            live_references=live_references,
        )

    missing = set(awaited) - observed_awaits
    if missing:
        first = awaited[min(missing)]
        raise SemanticError(
            "await keyword did not bind to a parsed direct call expression",
            first.keyword_location,
            diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        )


def lower_async_program(
    program: ast.Program,
    syntax: AsyncSyntaxTree,
) -> tuple[AsyncStateMachinePlan, ...]:
    """Produce deterministic compiler state-machine plans in declaration order."""

    awaited = {item.call_location.offset: item for item in syntax.awaits}
    async_names = syntax.async_function_names
    plans: list[AsyncStateMachinePlan] = []
    for function in program.functions:
        if function.name not in async_names:
            continue
        call_offsets = _await_offsets_in_block(function.body, awaited)
        suspension_points = tuple(
            AsyncSuspensionPoint(
                index=index,
                call_offset=offset,
                callee=awaited[offset].callee,
                suspended_state=f"suspended_{index}",
                resume_state=f"running_{index + 1}",
            )
            for index, offset in enumerate(call_offsets)
        )
        states: list[str] = ["created", "running_0"]
        for point in suspension_points:
            states.extend((point.suspended_state, point.resume_state))
        states.extend(("completed", "failed", "cancelled"))
        plans.append(
            AsyncStateMachinePlan(
                function.name,
                _frame_slots(function),
                suspension_points,
                tuple(states),
            )
        )
    return tuple(plans)


def _token_at(tokens: tuple[Token, ...], index: int) -> Token:
    if index < 0 or index >= len(tokens):
        return tokens[-1]
    return tokens[index]


def _replace_with_spaces(source: str, replacements: list[tuple[int, int]]) -> str:
    characters = list(source)
    for start, length in replacements:
        for index in range(start, start + length):
            characters[index] = " "
    return "".join(characters)


def _validate_syntax_bindings(program: ast.Program, syntax: AsyncSyntaxTree) -> None:
    by_name = {function.name: function for function in program.functions}
    seen: set[str] = set()
    for item in syntax.functions:
        if item.name in seen:
            raise SemanticError(
                f"duplicate async function marker for '{item.name}'",
                item.keyword_location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )
        seen.add(item.name)
        function = by_name.get(item.name)
        if function is None or function.location.offset != item.function_location.offset:
            raise SemanticError(
                f"async marker is not attached to function '{item.name}'",
                item.keyword_location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )


def _validate_block(
    block: ast.Block,
    *,
    function_name: str,
    function_is_async: bool,
    async_names: frozenset[str],
    awaited: dict[int, AwaitSyntax],
    observed_awaits: set[int],
    live_references: set[str],
) -> None:
    local_references = set(live_references)
    for statement in block.statements:
        if isinstance(statement, ast.VariableDeclaration):
            _validate_initializer(
                statement.initializer,
                function_name,
                function_is_async,
                async_names,
                awaited,
                observed_awaits,
                local_references,
            )
            if isinstance(statement.type_name, (ast.ReferenceType, ast.SliceType)):
                local_references.add(statement.name)
            continue
        if isinstance(statement, (ast.AssignmentStatement, ast.CompoundAssignmentStatement)):
            _validate_target(
                statement.target,
                function_name,
                function_is_async,
                async_names,
                awaited,
                observed_awaits,
                local_references,
            )
            _validate_initializer(
                statement.value,
                function_name,
                function_is_async,
                async_names,
                awaited,
                observed_awaits,
                local_references,
            )
            continue
        if isinstance(statement, (ast.ReturnStatement, ast.DiscardStatement)):
            _validate_expression(
                statement.expression,
                function_name,
                function_is_async,
                async_names,
                awaited,
                observed_awaits,
                local_references,
            )
            continue
        if isinstance(statement, ast.SwitchStatement):
            _validate_expression(
                statement.expression,
                function_name,
                function_is_async,
                async_names,
                awaited,
                observed_awaits,
                local_references,
            )
            for case in statement.cases:
                _validate_block(
                    case.body,
                    function_name=function_name,
                    function_is_async=function_is_async,
                    async_names=async_names,
                    awaited=awaited,
                    observed_awaits=observed_awaits,
                    live_references=set(local_references),
                )
            continue
        if isinstance(statement, ast.WhileStatement):
            _validate_expression(
                statement.condition,
                function_name,
                function_is_async,
                async_names,
                awaited,
                observed_awaits,
                local_references,
            )
            _validate_block(
                statement.body,
                function_name=function_name,
                function_is_async=function_is_async,
                async_names=async_names,
                awaited=awaited,
                observed_awaits=observed_awaits,
                live_references=set(local_references),
            )
            continue
        if isinstance(statement, ast.ForStatement):
            for expression in (
                statement.start_expression,
                statement.end_expression,
                statement.step_expression,
            ):
                _validate_expression(
                    expression,
                    function_name,
                    function_is_async,
                    async_names,
                    awaited,
                    observed_awaits,
                    local_references,
                )
            _validate_block(
                statement.body,
                function_name=function_name,
                function_is_async=function_is_async,
                async_names=async_names,
                awaited=awaited,
                observed_awaits=observed_awaits,
                live_references=set(local_references),
            )


def _validate_target(
    target: ast.AssignmentTarget,
    function_name: str,
    function_is_async: bool,
    async_names: frozenset[str],
    awaited: dict[int, AwaitSyntax],
    observed_awaits: set[int],
    live_references: set[str],
) -> None:
    expressions: list[ast.Expression] = []
    if isinstance(target, ast.IndexTarget):
        expressions.append(target.index)
    elif isinstance(target, ast.DereferenceTarget):
        expressions.append(target.reference)
    elif isinstance(target, ast.FieldTarget):
        expressions.append(target.target)
    for expression in expressions:
        _validate_expression(
            expression,
            function_name,
            function_is_async,
            async_names,
            awaited,
            observed_awaits,
            live_references,
        )


def _validate_initializer(
    initializer: ast.Initializer,
    function_name: str,
    function_is_async: bool,
    async_names: frozenset[str],
    awaited: dict[int, AwaitSyntax],
    observed_awaits: set[int],
    live_references: set[str],
) -> None:
    if isinstance(initializer, ast.ArrayLiteral):
        for element in initializer.elements:
            _validate_expression(
                element,
                function_name,
                function_is_async,
                async_names,
                awaited,
                observed_awaits,
                live_references,
            )
    else:
        _validate_expression(
            initializer,
            function_name,
            function_is_async,
            async_names,
            awaited,
            observed_awaits,
            live_references,
        )


def _validate_expression(
    expression: ast.Expression,
    function_name: str,
    function_is_async: bool,
    async_names: frozenset[str],
    awaited: dict[int, AwaitSyntax],
    observed_awaits: set[int],
    live_references: set[str],
) -> None:
    if isinstance(expression, ast.CallExpression):
        offset = expression.location.offset
        marker = awaited.get(offset)
        callee = expression.simple_function_name
        if marker is not None:
            observed_awaits.add(offset)
            if not function_is_async:
                raise SemanticError(
                    f"await is only valid inside async fn; '{function_name}' is synchronous",
                    marker.keyword_location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
                )
            if callee != marker.callee or callee not in async_names:
                raise SemanticError(
                    f"await target '{marker.callee}' is not an async function",
                    marker.keyword_location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
                )
            if live_references:
                names = ", ".join(sorted(live_references))
                raise SemanticError(
                    "ordinary lexical reference/slice is live across await: " + names,
                    marker.keyword_location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
                )
        elif callee in async_names:
            raise SemanticError(
                f"call to async function '{callee}' must be awaited",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )
        if expression.simple_function_name is None:
            _validate_expression(
                expression.callee,
                function_name,
                function_is_async,
                async_names,
                awaited,
                observed_awaits,
                live_references,
            )
        for argument in expression.arguments:
            _validate_expression(
                argument.expression,
                function_name,
                function_is_async,
                async_names,
                awaited,
                observed_awaits,
                live_references,
            )
        return
    if isinstance(expression, ast.RecordExpression):
        for field in expression.fields:
            _validate_expression(
                field.expression,
                function_name,
                function_is_async,
                async_names,
                awaited,
                observed_awaits,
                live_references,
            )
        return
    if isinstance(expression, ast.GenericTypeExpression):
        _validate_expression(
            expression.target,
            function_name,
            function_is_async,
            async_names,
            awaited,
            observed_awaits,
            live_references,
        )
        return
    if isinstance(expression, ast.IndexExpression):
        children = (expression.target, expression.index)
    elif isinstance(expression, ast.SliceExpression):
        children = (expression.target, expression.start, expression.end)
    elif isinstance(expression, ast.FieldAccessExpression):
        children = (expression.target,)
    elif isinstance(expression, (ast.AddressOfExpression, ast.DereferenceExpression)):
        children = (expression.operand,)
    elif isinstance(expression, ast.UnaryExpression):
        children = (expression.operand,)
    elif isinstance(expression, ast.BinaryExpression):
        children = (expression.left, expression.right)
    elif isinstance(expression, ast.MatchExpression):
        children = (expression.selector, *(case.expression for case in expression.cases))
    elif isinstance(expression, ast.LenExpression):
        children = (expression.argument,)
    else:
        children = ()
    for child in children:
        _validate_expression(
            child,
            function_name,
            function_is_async,
            async_names,
            awaited,
            observed_awaits,
            live_references,
        )


def _await_offsets_in_block(
    block: ast.Block,
    awaited: dict[int, AwaitSyntax],
) -> tuple[int, ...]:
    offsets: list[int] = []

    def visit_expression(expression: ast.Expression) -> None:
        if isinstance(expression, ast.CallExpression):
            if expression.location.offset in awaited:
                offsets.append(expression.location.offset)
            if expression.simple_function_name is None:
                visit_expression(expression.callee)
            for argument in expression.arguments:
                visit_expression(argument.expression)
            return
        if isinstance(expression, ast.RecordExpression):
            for field in expression.fields:
                visit_expression(field.expression)
            return
        if isinstance(expression, ast.GenericTypeExpression):
            visit_expression(expression.target)
            return
        if isinstance(expression, ast.IndexExpression):
            children = (expression.target, expression.index)
        elif isinstance(expression, ast.SliceExpression):
            children = (expression.target, expression.start, expression.end)
        elif isinstance(expression, ast.FieldAccessExpression):
            children = (expression.target,)
        elif isinstance(expression, (ast.AddressOfExpression, ast.DereferenceExpression)):
            children = (expression.operand,)
        elif isinstance(expression, ast.UnaryExpression):
            children = (expression.operand,)
        elif isinstance(expression, ast.BinaryExpression):
            children = (expression.left, expression.right)
        elif isinstance(expression, ast.MatchExpression):
            children = (expression.selector, *(case.expression for case in expression.cases))
        elif isinstance(expression, ast.LenExpression):
            children = (expression.argument,)
        else:
            children = ()
        for child in children:
            visit_expression(child)

    def visit_initializer(initializer: ast.Initializer) -> None:
        if isinstance(initializer, ast.ArrayLiteral):
            for element in initializer.elements:
                visit_expression(element)
        else:
            visit_expression(initializer)

    def visit_block(current: ast.Block) -> None:
        for statement in current.statements:
            if isinstance(statement, ast.VariableDeclaration):
                visit_initializer(statement.initializer)
            elif isinstance(statement, (ast.AssignmentStatement, ast.CompoundAssignmentStatement)):
                visit_initializer(statement.value)
            elif isinstance(statement, (ast.ReturnStatement, ast.DiscardStatement)):
                visit_expression(statement.expression)
            elif isinstance(statement, ast.SwitchStatement):
                visit_expression(statement.expression)
                for case in statement.cases:
                    visit_block(case.body)
            elif isinstance(statement, ast.WhileStatement):
                visit_expression(statement.condition)
                visit_block(statement.body)
            elif isinstance(statement, ast.ForStatement):
                visit_expression(statement.start_expression)
                visit_expression(statement.end_expression)
                visit_expression(statement.step_expression)
                visit_block(statement.body)

    visit_block(block)
    return tuple(offsets)


def _frame_slots(function: ast.FunctionDeclaration) -> tuple[str, ...]:
    slots: list[str] = [
        f"param:{parameter.name}@{parameter.location.offset}"
        for parameter in function.parameters
    ]

    def visit(block: ast.Block) -> None:
        for statement in block.statements:
            if isinstance(statement, ast.VariableDeclaration):
                slots.append(f"local:{statement.name}@{statement.location.offset}")
            elif isinstance(statement, ast.SwitchStatement):
                for case in statement.cases:
                    visit(case.body)
            elif isinstance(statement, ast.WhileStatement):
                visit(statement.body)
            elif isinstance(statement, ast.ForStatement):
                slots.append(
                    f"loop:{statement.variable_name}@{statement.location.offset}"
                )
                visit(statement.body)

    visit(function.body)
    return tuple(slots)
