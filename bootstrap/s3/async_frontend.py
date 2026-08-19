"""First-class bounded async syntax front-end and suspension-plan lowering for M1.71.

The existing recursive-descent parser remains the core S3 grammar parser. This
module recognizes contextual ``async`` and ``await`` markers from the original
token stream, removes only those marker spans before delegating to the core
parser, maps the parsed offsets back to the original source, validates
async-specific semantics, and emits deterministic suspension plans.

M1.71 V1 keeps Future values implicit: an async function call must be
immediately awaited. This avoids a general Future type or new lifetime syntax
while making ``async fn`` / ``await`` source-visible and compiler-checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from . import ast
from .diagnostics import DiagnosticCode, ParseError, SemanticError, SourceLocation
from .lexer import SyntaxMode, Token, TokenKind, tokenize
from .parser import parse_tokens


@dataclass(frozen=True, slots=True)
class AsyncFunctionSyntax:
    name: str
    keyword_location: SourceLocation
    function_location: SourceLocation
    parsed_function_offset: int


@dataclass(frozen=True, slots=True)
class AwaitSyntax:
    keyword_location: SourceLocation
    call_location: SourceLocation
    callee: str
    parsed_call_offset: int


@dataclass(frozen=True, slots=True)
class AsyncSyntaxTree:
    """Async-specific syntax side tree with original source locations."""

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
    lowering_model: str = "compiler_async_ir_with_hosted_resumable_execution"


def parse_async_source(
    source: str,
    *,
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> ParsedAsyncSource:
    """Parse S3 source including ``async fn`` and ``await direct_call()``."""

    original_tokens = tokenize(source, mode=mode)
    raw_functions: list[tuple[str, SourceLocation, SourceLocation]] = []
    raw_awaits: list[tuple[SourceLocation, SourceLocation, str]] = []
    deletions: list[tuple[int, int]] = []

    for index, token in enumerate(original_tokens):
        if token.kind is not TokenKind.IDENTIFIER or token.text not in {"async", "await"}:
            continue
        if mode is not SyntaxMode.V0_6:
            raise ParseError(
                "async/await requires source syntax 0.6",
                token.location,
            )
        if token.text == "async":
            fn_token = _token_at(original_tokens, index + 1)
            name_token = _token_at(original_tokens, index + 2)
            if fn_token.kind is not TokenKind.FN or name_token.kind is not TokenKind.IDENTIFIER:
                raise ParseError(
                    "'async' is reserved for 'async fn' in M1.71",
                    token.location,
                )
            raw_functions.append((name_token.text, token.location, fn_token.location))
            deletions.append((token.position, fn_token.position))
            continue

        callee = _token_at(original_tokens, index + 1)
        open_paren = _token_at(original_tokens, index + 2)
        if callee.kind is not TokenKind.IDENTIFIER or open_paren.kind is not TokenKind.LEFT_PAREN:
            raise ParseError(
                "M1.71 await requires a direct function call",
                token.location,
            )
        raw_awaits.append((token.location, callee.location, callee.text))
        deletions.append((token.position, callee.position))

    spans = _validated_spans(deletions)
    transformed = _delete_spans(source, spans)
    transformed_tokens = tokenize(transformed, mode=mode)
    program = parse_tokens(transformed_tokens, mode=mode)

    functions = tuple(
        AsyncFunctionSyntax(
            name,
            keyword_location,
            function_location,
            _mapped_offset(function_location.offset, spans),
        )
        for name, keyword_location, function_location in raw_functions
    )
    awaits = tuple(
        AwaitSyntax(
            keyword_location,
            call_location,
            callee,
            _mapped_offset(call_location.offset, spans),
        )
        for keyword_location, call_location, callee in raw_awaits
    )
    syntax = AsyncSyntaxTree(
        functions,
        awaits,
        sha256(source.encode("utf-8")).hexdigest(),
    )
    _validate_syntax_bindings(program, syntax)
    return ParsedAsyncSource(original_tokens, program, syntax)


def validate_async_semantics(program: ast.Program, syntax: AsyncSyntaxTree) -> None:
    """Validate fail-closed M1.71 semantics before the core type analyzer."""

    async_names = syntax.async_function_names
    awaited = {item.parsed_call_offset: item for item in syntax.awaits}
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
        marker = awaited[min(missing)]
        raise SemanticError(
            "await keyword did not bind to a parsed direct call expression",
            marker.keyword_location,
            diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        )


def lower_async_program(
    program: ast.Program,
    syntax: AsyncSyntaxTree,
) -> tuple[AsyncStateMachinePlan, ...]:
    """Produce deterministic compiler state-machine plans in declaration order."""

    awaited = {item.parsed_call_offset: item for item in syntax.awaits}
    async_names = syntax.async_function_names
    plans: list[AsyncStateMachinePlan] = []
    for function in program.functions:
        if function.name not in async_names:
            continue
        parsed_offsets = tuple(
            expression.location.offset
            for expression in _iter_block_expressions(function.body)
            if isinstance(expression, ast.CallExpression)
            and expression.location.offset in awaited
        )
        points = tuple(
            AsyncSuspensionPoint(
                index=index,
                call_offset=awaited[offset].call_location.offset,
                callee=awaited[offset].callee,
                suspended_state=f"suspended_{index}",
                resume_state=f"running_{index + 1}",
            )
            for index, offset in enumerate(parsed_offsets)
        )
        states: list[str] = ["created", "running_0"]
        for point in points:
            states.extend((point.suspended_state, point.resume_state))
        states.extend(("completed", "failed", "cancelled"))
        plans.append(
            AsyncStateMachinePlan(
                function.name,
                _frame_slots(function),
                points,
                tuple(states),
            )
        )
    return tuple(plans)


def _token_at(tokens: tuple[Token, ...], index: int) -> Token:
    if index < 0 or index >= len(tokens):
        return tokens[-1]
    return tokens[index]


def _validated_spans(spans: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    ordered = tuple(sorted(spans))
    previous_end = -1
    for start, end in ordered:
        if start < 0 or end <= start or start < previous_end:
            raise ValueError("async keyword deletion spans overlap or are invalid")
        previous_end = end
    return ordered


def _delete_spans(source: str, spans: tuple[tuple[int, int], ...]) -> str:
    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        pieces.append(source[cursor:start])
        cursor = end
    pieces.append(source[cursor:])
    return "".join(pieces)


def _mapped_offset(original_offset: int, spans: tuple[tuple[int, int], ...]) -> int:
    removed = 0
    for start, end in spans:
        if end <= original_offset:
            removed += end - start
            continue
        if start < original_offset < end:
            return start - removed
        break
    return original_offset - removed


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
        if function is None or function.location.offset != item.parsed_function_offset:
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
            _validate_initializer(statement.initializer, function_name, function_is_async, async_names, awaited, observed_awaits, local_references)
            if isinstance(statement.type_name, (ast.ReferenceType, ast.SliceType)):
                local_references.add(statement.name)
        elif isinstance(statement, (ast.AssignmentStatement, ast.CompoundAssignmentStatement)):
            for expression in _target_expressions(statement.target):
                _validate_expression(expression, function_name, function_is_async, async_names, awaited, observed_awaits, local_references)
            _validate_initializer(statement.value, function_name, function_is_async, async_names, awaited, observed_awaits, local_references)
        elif isinstance(statement, (ast.ReturnStatement, ast.DiscardStatement)):
            _validate_expression(statement.expression, function_name, function_is_async, async_names, awaited, observed_awaits, local_references)
        elif isinstance(statement, ast.SwitchStatement):
            _validate_expression(statement.expression, function_name, function_is_async, async_names, awaited, observed_awaits, local_references)
            for case in statement.cases:
                _validate_block(case.body, function_name=function_name, function_is_async=function_is_async, async_names=async_names, awaited=awaited, observed_awaits=observed_awaits, live_references=set(local_references))
        elif isinstance(statement, ast.WhileStatement):
            _validate_expression(statement.condition, function_name, function_is_async, async_names, awaited, observed_awaits, local_references)
            _validate_block(statement.body, function_name=function_name, function_is_async=function_is_async, async_names=async_names, awaited=awaited, observed_awaits=observed_awaits, live_references=set(local_references))
        elif isinstance(statement, ast.ForStatement):
            for expression in (statement.start_expression, statement.end_expression, statement.step_expression):
                _validate_expression(expression, function_name, function_is_async, async_names, awaited, observed_awaits, local_references)
            _validate_block(statement.body, function_name=function_name, function_is_async=function_is_async, async_names=async_names, awaited=awaited, observed_awaits=observed_awaits, live_references=set(local_references))


def _validate_initializer(
    initializer: ast.Initializer,
    function_name: str,
    function_is_async: bool,
    async_names: frozenset[str],
    awaited: dict[int, AwaitSyntax],
    observed_awaits: set[int],
    live_references: set[str],
) -> None:
    expressions = initializer.elements if isinstance(initializer, ast.ArrayLiteral) else (initializer,)
    for expression in expressions:
        _validate_expression(expression, function_name, function_is_async, async_names, awaited, observed_awaits, live_references)


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
        marker = awaited.get(expression.location.offset)
        callee = expression.simple_function_name
        if marker is not None:
            observed_awaits.add(expression.location.offset)
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
                raise SemanticError(
                    "ordinary lexical reference/slice is live across await: " + ", ".join(sorted(live_references)),
                    marker.keyword_location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
                )
        elif callee in async_names:
            raise SemanticError(
                f"call to async function '{callee}' must be awaited",
                expression.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )
    for child in _child_expressions(expression):
        _validate_expression(child, function_name, function_is_async, async_names, awaited, observed_awaits, live_references)


def _child_expressions(expression: ast.Expression) -> tuple[ast.Expression, ...]:
    if isinstance(expression, ast.CallExpression):
        children = [argument.expression for argument in expression.arguments]
        if expression.simple_function_name is None:
            children.insert(0, expression.callee)
        return tuple(children)
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


def _target_expressions(target: ast.AssignmentTarget) -> tuple[ast.Expression, ...]:
    if isinstance(target, ast.IndexTarget):
        return (target.index,)
    if isinstance(target, ast.DereferenceTarget):
        return (target.reference,)
    if isinstance(target, ast.FieldTarget):
        return (target.target,)
    return ()


def _iter_expression_tree(expression: ast.Expression) -> Iterable[ast.Expression]:
    yield expression
    for child in _child_expressions(expression):
        yield from _iter_expression_tree(child)


def _iter_block_expressions(block: ast.Block) -> Iterable[ast.Expression]:
    for statement in block.statements:
        direct: tuple[ast.Expression, ...] = ()
        nested: tuple[ast.Block, ...] = ()
        if isinstance(statement, ast.VariableDeclaration):
            direct = statement.initializer.elements if isinstance(statement.initializer, ast.ArrayLiteral) else (statement.initializer,)
        elif isinstance(statement, (ast.AssignmentStatement, ast.CompoundAssignmentStatement)):
            value = statement.value.elements if isinstance(statement.value, ast.ArrayLiteral) else (statement.value,)
            direct = (*_target_expressions(statement.target), *value)
        elif isinstance(statement, (ast.ReturnStatement, ast.DiscardStatement)):
            direct = (statement.expression,)
        elif isinstance(statement, ast.SwitchStatement):
            direct = (statement.expression,)
            nested = tuple(case.body for case in statement.cases)
        elif isinstance(statement, ast.WhileStatement):
            direct = (statement.condition,)
            nested = (statement.body,)
        elif isinstance(statement, ast.ForStatement):
            direct = (statement.start_expression, statement.end_expression, statement.step_expression)
            nested = (statement.body,)
        for expression in direct:
            yield from _iter_expression_tree(expression)
        for child_block in nested:
            yield from _iter_block_expressions(child_block)


def _frame_slots(function: ast.FunctionDeclaration) -> tuple[str, ...]:
    slots: list[str] = [f"param:{parameter.name}@{parameter.location.offset}" for parameter in function.parameters]

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
                slots.append(f"loop:{statement.variable_name}@{statement.location.offset}")
                visit(statement.body)

    visit(function.body)
    return tuple(slots)
