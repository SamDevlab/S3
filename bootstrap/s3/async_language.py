"""Compiler-owned async language model for M1.81/M1.82.

This module keeps the stable V0.6 parser authoritative by removing contextual
``async``/``await`` tokens and erasing the ownership-only ``Future<T>`` wrapper
before core parsing.  The removed syntax is retained as deterministic compiler
metadata and lowered to executable, move-checked async actions.

The executable subset is deliberately fail-closed: async bodies are linear in
V1 (declarations, assignments, discard, return).  Control-flow containing
suspension requires an explicit async-CFG lowering rather than silently falling
back to synchronous direct calls.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256

from . import ast
from .async_limits import MAX_SELECT_ARITY, MAX_SELECT_DEPTH
from .diagnostics import DiagnosticCode, ParseError, SemanticError, SourceLocation
from .lexer import SyntaxMode, Token, TokenKind, tokenize
from .module_graph import ModuleId, normalize_logical_path
from .parser import parse_tokens


@dataclass(frozen=True, slots=True)
class AsyncFunctionMarker:
    name: str
    keyword_location: SourceLocation
    parsed_function_offset: int


@dataclass(frozen=True, slots=True)
class AsyncAwaitMarker:
    keyword_location: SourceLocation
    expression_name: str
    parsed_expression_offset: int


@dataclass(frozen=True, slots=True)
class FutureTypeMarker:
    name: str | None
    inner_type_text: str
    original_name_offset: int | None
    parsed_name_offset: int | None


@dataclass(frozen=True, slots=True)
class AsyncLanguageSyntax:
    functions: tuple[AsyncFunctionMarker, ...] = ()
    awaits: tuple[AsyncAwaitMarker, ...] = ()
    futures: tuple[FutureTypeMarker, ...] = ()
    source_sha256: str = ""

    @property
    def async_function_names(self) -> frozenset[str]:
        return frozenset(item.name for item in self.functions)

    @property
    def await_call_offsets(self) -> frozenset[int]:
        return frozenset(item.parsed_expression_offset for item in self.awaits)


@dataclass(frozen=True, slots=True)
class ParsedAsyncLanguageSource:
    tokens: tuple[Token, ...]
    program: ast.Program
    syntax: AsyncLanguageSyntax
    core_source: str


class AsyncExpressionKind(Enum):
    LITERAL = "literal"
    SLOT = "slot"
    FUTURE_MOVE = "future_move"
    UNARY = "unary"
    BINARY = "binary"
    SYNC_CALL = "sync_call"


@dataclass(frozen=True, slots=True)
class AsyncExpression:
    kind: AsyncExpressionKind
    value: object | None = None
    name: str | None = None
    operator: str | None = None
    arguments: tuple[AsyncExpression, ...] = ()
    type_arguments: tuple[str, ...] = ()


class AsyncActionKind(Enum):
    ASSIGN = "assign"
    FUTURE_CREATE = "future_create"
    FUTURE_MOVE = "future_move"
    AWAIT_CALL = "await_call"
    AWAIT_FUTURE = "await_future"
    SELECT = "select"
    RETURN = "return"
    DISCARD = "discard"


@dataclass(frozen=True, slots=True)
class AsyncSelectArm:
    callee: str | None = None
    arguments: tuple[AsyncExpression, ...] = ()
    source_future: str | None = None
    actions: tuple[AsyncAction, ...] = ()
    source_offset: int = 0


@dataclass(frozen=True, slots=True)
class AsyncAction:
    kind: AsyncActionKind
    target: str | None = None
    expression: AsyncExpression | None = None
    callee: str | None = None
    arguments: tuple[AsyncExpression, ...] = ()
    source_future: str | None = None
    return_after: bool = False
    type_arguments: tuple[str, ...] = ()
    source_offset: int = 0
    select_arms: tuple[AsyncSelectArm, ...] = ()


@dataclass(frozen=True, slots=True)
class AsyncExecutableFunction:
    name: str
    source_name: str
    parameters: tuple[str, ...]
    future_parameters: tuple[str, ...]
    frame_slots: tuple[str, ...]
    actions: tuple[AsyncAction, ...]
    async_function: bool
    generic_parameters: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class AsyncExecutableProgram:
    functions: tuple[AsyncExecutableFunction, ...]
    entry: str = "main"

    def function(self, name: str) -> AsyncExecutableFunction | None:
        for function in self.functions:
            if function.name == name:
                return function
        return None


@dataclass(frozen=True, slots=True)
class AsyncModulePreparation:
    core_sources: tuple[tuple[str, str], ...]
    parsed_sources: tuple[tuple[str, ParsedAsyncLanguageSource], ...]
    executable: AsyncExecutableProgram


SourceCollection = Mapping[str, str] | Iterable[tuple[str, str]]


def parse_async_language_source(source: str, *, mode: SyntaxMode = SyntaxMode.V0_6) -> ParsedAsyncLanguageSource:
    if not isinstance(source, str):
        raise TypeError("source must be text")
    tokens = tokenize(source, mode=mode)
    async_raw: list[tuple[str, SourceLocation, int]] = []
    await_raw: list[tuple[SourceLocation, str, int]] = []
    future_raw: list[tuple[str | None, str, int | None]] = []
    spans: list[tuple[int, int]] = []

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind is TokenKind.IDENTIFIER and token.text == "async":
            if mode is not SyntaxMode.V0_6:
                raise ParseError("async/await requires source syntax 0.6", token.location)
            fn_token = _at(tokens, index + 1)
            name_token = _at(tokens, index + 2)
            if fn_token.kind is not TokenKind.FN or name_token.kind is not TokenKind.IDENTIFIER:
                raise ParseError("'async' is reserved for 'async fn'", token.location)
            async_raw.append((name_token.text, token.location, fn_token.position))
            spans.append((token.position, fn_token.position))
        elif token.kind is TokenKind.IDENTIFIER and token.text == "await":
            if mode is not SyntaxMode.V0_6:
                raise ParseError("async/await requires source syntax 0.6", token.location)
            target = _at(tokens, index + 1)
            if target.kind is not TokenKind.IDENTIFIER:
                raise ParseError("await requires an owned Future or direct async call", token.location)
            await_raw.append((token.location, target.text, target.position))
            spans.append((token.position, target.position))
        index += 1

    # Future<T> is a compile-time ownership wrapper.  Core semantic/lowering
    # receives T while this module retains the Future ownership marker.
    index = 0
    while index < len(tokens) - 1:
        token = tokens[index]
        if token.kind is TokenKind.IDENTIFIER and token.text == "Future" and _at(tokens, index + 1).kind is TokenKind.LESS:
            opening = index + 1
            closing = _matching_greater(tokens, opening)
            if closing <= opening + 1:
                raise ParseError("Future<T> requires one closed value type", token.location)
            depth = 0
            for inner in tokens[opening + 1 : closing]:
                if inner.kind is TokenKind.LESS:
                    depth += 1
                elif inner.kind is TokenKind.GREATER:
                    depth -= 1
                elif inner.kind is TokenKind.COMMA and depth == 0:
                    raise ParseError("Future<T> accepts exactly one type argument", inner.location)
            first_inner = tokens[opening + 1]
            close_token = tokens[closing]
            prefix = (token.position, first_inner.position)
            suffix = (close_token.position, close_token.position + max(1, len(close_token.text)))
            spans.extend((prefix, suffix))
            owner_name: str | None = None
            owner_offset: int | None = None
            if index >= 2 and tokens[index - 1].kind is TokenKind.COLON and tokens[index - 2].kind is TokenKind.IDENTIFIER:
                owner_name = tokens[index - 2].text
                owner_offset = tokens[index - 2].position
            inner_text = source[first_inner.position : close_token.position].strip()
            future_raw.append((owner_name, inner_text, owner_offset))
            index = closing
        index += 1

    validated = _validated_spans(spans)
    core_source = _delete_spans(source, validated)
    core_tokens = tokenize(core_source, mode=mode)
    program = parse_tokens(core_tokens, mode=mode)
    functions = tuple(
        AsyncFunctionMarker(name, location, _mapped_offset(fn_offset, validated))
        for name, location, fn_offset in async_raw
    )
    awaits = tuple(
        AsyncAwaitMarker(location, name, _mapped_offset(expression_offset, validated))
        for location, name, expression_offset in await_raw
    )
    futures = tuple(
        FutureTypeMarker(
            name,
            inner,
            owner_offset,
            None if owner_offset is None else _mapped_offset(owner_offset, validated),
        )
        for name, inner, owner_offset in future_raw
    )
    syntax = AsyncLanguageSyntax(functions, awaits, futures, sha256(source.encode("utf-8")).hexdigest())
    _bind_async_functions(program, syntax)
    return ParsedAsyncLanguageSource(tokens, program, syntax, core_source)


def lower_async_language_program(
    parsed: ParsedAsyncLanguageSource,
    *,
    name_map: Mapping[str, str] | None = None,
    call_map: Mapping[str, str] | None = None,
) -> AsyncExecutableProgram:
    """Validate Future ownership and lower source-visible async constructs."""

    program = parsed.program
    syntax = parsed.syntax
    async_names = syntax.async_function_names
    functions = {function.name: function for function in program.functions}
    await_by_offset = {item.parsed_expression_offset: item for item in syntax.awaits}
    future_names = {item.name for item in syntax.futures if item.name is not None}
    mapped_names = dict(name_map or {})
    mapped_calls = dict(call_map or {})
    executable: list[AsyncExecutableFunction] = []
    observed_awaits: set[int] = set()

    for async_name in async_names:
        if async_name not in functions:
            raise SemanticError(
                f"async marker does not resolve to function '{async_name}'",
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )

    for function in program.functions:
        is_async = function.name in async_names
        function_future_names = {
            parameter.name for parameter in function.parameters if parameter.name in future_names
        }
        function_future_names.update(_future_declarations(function.body, future_names))
        if not is_async and not function_future_names:
            continue
        if not is_async and _block_has_await(function.body, await_by_offset):
            raise SemanticError(
                "await is only valid inside async fn",
                function.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )
        if is_async and _contains_control_flow(function.body):
            raise SemanticError(
                "M1.81 V1 requires linear async bodies; suspension inside control flow needs explicit async CFG lowering",
                function.location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )
        actions = _lower_block_actions(
            function,
            async_names=async_names,
            await_by_offset=await_by_offset,
            future_names=function_future_names,
            observed_awaits=observed_awaits,
            call_map=mapped_calls,
        )
        internal_name = mapped_names.get(function.name, function.name)
        frame_slots = tuple(parameter.name for parameter in function.parameters) + _frame_local_names(function.body)
        executable.append(
            AsyncExecutableFunction(
                internal_name,
                function.name,
                tuple(parameter.name for parameter in function.parameters),
                tuple(parameter.name for parameter in function.parameters if parameter.name in function_future_names),
                frame_slots,
                actions,
                is_async,
                tuple((item.name, item.constraint) for item in function.signature.type_parameters),
            )
        )

    missing = set(await_by_offset) - observed_awaits
    if missing:
        marker = await_by_offset[min(missing)]
        raise SemanticError(
            "await marker is not a complete supported initializer/return/discard expression",
            marker.keyword_location,
            diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        )
    return AsyncExecutableProgram(tuple(executable))


def prepare_async_module_sources(
    sources: SourceCollection,
    *,
    entry_module: str = "main",
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> AsyncModulePreparation:
    items = _source_items(sources)
    parsed_items = tuple((path, parse_async_language_source(source, mode=mode)) for path, source in items)
    module_by_path: dict[str, ModuleId] = {}
    parsed_by_module: dict[ModuleId, ParsedAsyncLanguageSource] = {}
    for path, parsed in parsed_items:
        module = ModuleId.parse(parsed.program.module.name if parsed.program.module is not None else _module_from_path(path))
        if module in parsed_by_module:
            raise SemanticError(f"duplicate module '{module}'", diagnostic_code=DiagnosticCode.MODULE_DUPLICATE)
        module_by_path[path] = module
        parsed_by_module[module] = parsed
    entry = ModuleId.parse(entry_module)

    async_identity: dict[tuple[ModuleId, str], str] = {}
    for module, parsed in parsed_by_module.items():
        for function in parsed.program.functions:
            async_identity[(module, function.name)] = _internal_function_name(module, function.name, entry)

    all_exec: list[AsyncExecutableFunction] = []
    for path, parsed in parsed_items:
        module = module_by_path[path]
        name_map = {
            function.name: async_identity[(module, function.name)]
            for function in parsed.program.functions
        }
        call_map = dict(name_map)
        for imported in parsed.program.imports:
            target_module = ModuleId.parse(imported.module_name)
            key = (target_module, imported.symbol_name)
            if key not in async_identity:
                # Core module compilation will emit the authoritative unknown
                # import diagnostic.  Do not invent a second namespace.
                continue
            call_map[imported.alias or imported.symbol_name] = async_identity[key]
        lowered = lower_async_language_program(parsed, name_map=name_map, call_map=call_map)
        all_exec.extend(lowered.functions)
    return AsyncModulePreparation(
        tuple((path, parsed.core_source) for path, parsed in parsed_items),
        parsed_items,
        AsyncExecutableProgram(tuple(all_exec), entry="main"),
    )


def _lower_block_actions(
    function: ast.FunctionDeclaration,
    *,
    async_names: frozenset[str],
    await_by_offset: dict[int, AsyncAwaitMarker],
    future_names: set[str],
    observed_awaits: set[int],
    call_map: Mapping[str, str],
    block: ast.Block | None = None,
    future_state: dict[str, str] | None = None,
    select_depth: int = 0,
) -> tuple[AsyncAction, ...]:
    actions: list[AsyncAction] = []
    state = future_state if future_state is not None else {
        parameter.name: "live" for parameter in function.parameters if parameter.name in future_names
    }
    current_block = function.body if block is None else block
    for statement in current_block.statements:
        if isinstance(statement, ast.VariableDeclaration):
            expression = _single_initializer(statement.initializer, statement.location)
            marker = await_by_offset.get(expression.location.offset)
            if statement.name in future_names:
                if marker is not None:
                    raise SemanticError("Future<T> binding cannot store an already-awaited value", marker.keyword_location)
                if isinstance(expression, ast.CallExpression) and expression.simple_function_name in async_names:
                    arguments = _compile_call_arguments(expression, state, future_names, async_names)
                    state[statement.name] = "live"
                    actions.append(
                        AsyncAction(
                            AsyncActionKind.FUTURE_CREATE,
                            target=statement.name,
                            callee=call_map.get(expression.simple_function_name, expression.simple_function_name),
                            arguments=arguments,
                            type_arguments=tuple(_type_key(item) for item in expression.type_arguments),
                            source_offset=statement.location.offset,
                        )
                    )
                    continue
                if isinstance(expression, ast.Identifier) and expression.name in future_names:
                    _require_future_live(expression.name, state, expression.location)
                    state[expression.name] = "moved"
                    state[statement.name] = "live"
                    actions.append(
                        AsyncAction(
                            AsyncActionKind.FUTURE_MOVE,
                            target=statement.name,
                            source_future=expression.name,
                            source_offset=statement.location.offset,
                        )
                    )
                    continue
                raise SemanticError("Future<T> must be created from an async call or moved from another Future", statement.location)
            if marker is not None:
                observed_awaits.add(expression.location.offset)
                actions.append(_await_action(expression, marker, statement.name, False, state, future_names, async_names, call_map))
            else:
                actions.append(
                    AsyncAction(
                        AsyncActionKind.ASSIGN,
                        target=statement.name,
                        expression=_compile_expression(expression, state, future_names, async_names),
                        source_offset=statement.location.offset,
                    )
                )
        elif isinstance(statement, ast.AssignmentStatement):
            if not isinstance(statement.target, ast.VariableTarget):
                raise SemanticError("M1.81 executable async IR supports variable assignment targets only", statement.location)
            expression = _single_initializer(statement.value, statement.location)
            target = statement.target.name
            marker = await_by_offset.get(expression.location.offset)
            if target in future_names:
                if state.get(target) == "live":
                    raise SemanticError("cannot overwrite a live move-only Future", statement.location)
                if not isinstance(expression, ast.Identifier) or expression.name not in future_names:
                    raise SemanticError("Future assignment requires an ownership move", statement.location)
                _require_future_live(expression.name, state, expression.location)
                state[expression.name] = "moved"
                state[target] = "live"
                actions.append(AsyncAction(AsyncActionKind.FUTURE_MOVE, target=target, source_future=expression.name, source_offset=statement.location.offset))
            elif marker is not None:
                observed_awaits.add(expression.location.offset)
                actions.append(_await_action(expression, marker, target, False, state, future_names, async_names, call_map))
            else:
                actions.append(AsyncAction(AsyncActionKind.ASSIGN, target=target, expression=_compile_expression(expression, state, future_names, async_names), source_offset=statement.location.offset))
        elif isinstance(statement, ast.ReturnStatement):
            expression = statement.expression
            marker = await_by_offset.get(expression.location.offset)
            if marker is not None:
                observed_awaits.add(expression.location.offset)
                actions.append(_await_action(expression, marker, None, True, state, future_names, async_names, call_map))
            else:
                actions.append(AsyncAction(AsyncActionKind.RETURN, expression=_compile_expression(expression, state, future_names, async_names), source_offset=statement.location.offset))
        elif isinstance(statement, ast.DiscardStatement):
            expression = statement.expression
            marker = await_by_offset.get(expression.location.offset)
            if marker is not None:
                observed_awaits.add(expression.location.offset)
                actions.append(_await_action(expression, marker, None, False, state, future_names, async_names, call_map, discard=True))
            else:
                actions.append(AsyncAction(AsyncActionKind.DISCARD, expression=_compile_expression(expression, state, future_names, async_names), source_offset=statement.location.offset))
        elif isinstance(statement, ast.SelectStatement):
            actions.append(
                _select_action(
                    function,
                    statement,
                    async_names=async_names,
                    await_by_offset=await_by_offset,
                    future_names=future_names,
                    future_state=state,
                    observed_awaits=observed_awaits,
                    call_map=call_map,
                    select_depth=select_depth,
                )
            )
        else:
            raise SemanticError("unsupported statement in executable async IR", statement.location, diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM)

    # A live Future may be dropped at function exit; moved/consumed owners are
    # not dropped again.  Runtime frame cleanup enforces exactly-once ownership.
    return tuple(actions)


def _select_action(
    function: ast.FunctionDeclaration,
    statement: ast.SelectStatement,
    *,
    async_names: frozenset[str],
    await_by_offset: dict[int, AsyncAwaitMarker],
    future_names: set[str],
    future_state: dict[str, str],
    observed_awaits: set[int],
    call_map: Mapping[str, str],
    select_depth: int,
) -> AsyncAction:
    if not 1 <= len(statement.arms) <= MAX_SELECT_ARITY:
        raise SemanticError(f"select requires between 1 and {MAX_SELECT_ARITY} arms", statement.location)
    if select_depth >= MAX_SELECT_DEPTH:
        raise SemanticError(f"select nesting exceeds bounded depth {MAX_SELECT_DEPTH}", statement.location)

    baseline = dict(future_state)
    selected_future_names: set[str] = set()
    arm_models: list[AsyncSelectArm] = []
    branch_states: list[dict[str, str]] = []
    for arm in statement.arms:
        branch_state = dict(baseline)
        marker = await_by_offset.get(arm.operation.location.offset)
        if marker is None:
            raise SemanticError("select operation must be explicitly awaited", arm.operation.location)
        observed_awaits.add(arm.operation.location.offset)
        callee, arguments, source_future = _select_operation(
            arm.operation,
            marker,
            async_names=async_names,
            future_names=future_names,
            future_state=branch_state,
            call_map=call_map,
        )
        if source_future is not None:
            selected_future_names.add(source_future)
        body_actions = _lower_block_actions(
            function,
            async_names=async_names,
            await_by_offset=await_by_offset,
            future_names=future_names,
            observed_awaits=observed_awaits,
            call_map=call_map,
            block=arm.body,
            future_state=branch_state,
            select_depth=select_depth + 1,
        )
        branch_states.append(branch_state)
        arm_models.append(
            AsyncSelectArm(
                callee=callee,
                arguments=arguments,
                source_future=source_future,
                actions=body_actions,
                source_offset=arm.location.offset,
            )
        )

    # Every candidate is consumed by the select decision.  This makes an
    # unselected Future unavailable after the join and prevents double-polling.
    for branch_state in branch_states:
        for name in selected_future_names:
            if branch_state.get(name) == "live":
                branch_state[name] = "consumed"
    first_state = branch_states[0]
    if any(state != first_state for state in branch_states[1:]):
        raise SemanticError(
            "owned-value state differs between select arms; reinitialize or consume every branch consistently",
            statement.location,
            diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        )
    future_state.clear()
    future_state.update(first_state)
    return AsyncAction(
        AsyncActionKind.SELECT,
        select_arms=tuple(arm_models),
        source_offset=statement.location.offset,
    )


def _select_operation(
    expression: ast.Expression,
    marker: AsyncAwaitMarker,
    *,
    async_names: frozenset[str],
    future_names: set[str],
    future_state: dict[str, str],
    call_map: Mapping[str, str],
) -> tuple[str | None, tuple[AsyncExpression, ...], str | None]:
    if isinstance(expression, ast.CallExpression):
        callee = expression.simple_function_name
        if callee is None or callee not in async_names:
            raise SemanticError(f"await target '{marker.expression_name}' is not an async function", marker.keyword_location)
        before = dict(future_state)
        arguments = _compile_call_arguments(expression, future_state, future_names, async_names)
        if future_state != before:
            raise SemanticError("select operation arguments cannot move a Future owner", expression.location)
        return call_map.get(callee, callee), arguments, None
    if isinstance(expression, ast.Identifier) and expression.name in future_names:
        _require_future_live(expression.name, future_state, expression.location)
        future_state[expression.name] = "consumed"
        return None, (), expression.name
    raise SemanticError("select requires direct async calls or owned Future variables", marker.keyword_location)


def _await_action(
    expression: ast.Expression,
    marker: AsyncAwaitMarker,
    target: str | None,
    return_after: bool,
    future_state: dict[str, str],
    future_names: set[str],
    async_names: frozenset[str],
    call_map: Mapping[str, str],
    *,
    discard: bool = False,
) -> AsyncAction:
    if isinstance(expression, ast.CallExpression):
        callee = expression.simple_function_name
        if callee is None or callee not in async_names:
            raise SemanticError(f"await target '{marker.expression_name}' is not an async function", marker.keyword_location)
        arguments = _compile_call_arguments(expression, future_state, future_names, async_names)
        return AsyncAction(
            AsyncActionKind.AWAIT_CALL if not discard else AsyncActionKind.DISCARD,
            target=target,
            callee=call_map.get(callee, callee),
            arguments=arguments,
            return_after=return_after,
            type_arguments=tuple(_type_key(item) for item in expression.type_arguments),
            source_offset=marker.keyword_location.offset,
        )
    if isinstance(expression, ast.Identifier) and expression.name in future_names:
        _require_future_live(expression.name, future_state, expression.location)
        future_state[expression.name] = "consumed"
        return AsyncAction(
            AsyncActionKind.AWAIT_FUTURE if not discard else AsyncActionKind.DISCARD,
            target=target,
            source_future=expression.name,
            return_after=return_after,
            source_offset=marker.keyword_location.offset,
        )
    raise SemanticError("await requires a direct async call or owned Future variable", marker.keyword_location)


def _compile_call_arguments(
    expression: ast.CallExpression,
    future_state: dict[str, str],
    future_names: set[str],
    async_names: frozenset[str],
) -> tuple[AsyncExpression, ...]:
    result: list[AsyncExpression] = []
    for argument in expression.arguments:
        value = argument.expression
        if isinstance(value, ast.Identifier) and value.name in future_names:
            _require_future_live(value.name, future_state, value.location)
            future_state[value.name] = "moved"
            result.append(AsyncExpression(AsyncExpressionKind.FUTURE_MOVE, name=value.name))
        else:
            result.append(_compile_expression(value, future_state, future_names, async_names))
    return tuple(result)


def _compile_expression(
    expression: ast.Expression,
    future_state: dict[str, str],
    future_names: set[str],
    async_names: frozenset[str],
) -> AsyncExpression:
    if isinstance(expression, ast.IntegerLiteral):
        return AsyncExpression(AsyncExpressionKind.LITERAL, value=expression.value)
    if isinstance(expression, ast.FloatLiteral):
        return AsyncExpression(AsyncExpressionKind.LITERAL, value=expression.value)
    if isinstance(expression, ast.StringLiteral):
        return AsyncExpression(AsyncExpressionKind.LITERAL, value=expression.value)
    if isinstance(expression, ast.Identifier):
        if expression.name in future_names:
            _require_future_live(expression.name, future_state, expression.location)
            raise SemanticError("Future is move-only and cannot be used as an ordinary value", expression.location)
        return AsyncExpression(AsyncExpressionKind.SLOT, name=expression.name)
    if isinstance(expression, ast.UnaryExpression):
        return AsyncExpression(AsyncExpressionKind.UNARY, operator=expression.operator.value, arguments=(_compile_expression(expression.operand, future_state, future_names, async_names),))
    if isinstance(expression, ast.BinaryExpression):
        return AsyncExpression(
            AsyncExpressionKind.BINARY,
            operator=expression.operator.value,
            arguments=(
                _compile_expression(expression.left, future_state, future_names, async_names),
                _compile_expression(expression.right, future_state, future_names, async_names),
            ),
        )
    if isinstance(expression, ast.CallExpression):
        callee = expression.simple_function_name
        if callee in async_names:
            raise SemanticError(f"call to async function '{callee}' must be awaited or stored in Future<T>", expression.location)
        if callee is None:
            raise SemanticError("indirect calls are outside executable async IR V1", expression.location)
        return AsyncExpression(
            AsyncExpressionKind.SYNC_CALL,
            name=callee,
            arguments=_compile_call_arguments(expression, future_state, future_names, async_names),
            type_arguments=tuple(_type_key(item) for item in expression.type_arguments),
        )
    raise SemanticError("expression is outside executable async IR V1", expression.location, diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM)


def _single_initializer(initializer: ast.Initializer, location: SourceLocation) -> ast.Expression:
    if isinstance(initializer, ast.ArrayLiteral):
        raise SemanticError("array initializer is outside executable async IR V1", location)
    return initializer


def _future_declarations(block: ast.Block, known: set[str]) -> set[str]:
    result: set[str] = set()
    for statement in block.statements:
        if isinstance(statement, ast.VariableDeclaration) and statement.name in known:
            result.add(statement.name)
        elif isinstance(statement, ast.SelectStatement):
            for arm in statement.arms:
                result.update(_future_declarations(arm.body, known))
        elif isinstance(statement, (ast.SwitchStatement,)):
            for case in statement.cases:
                result.update(_future_declarations(case.body, known))
        elif isinstance(statement, (ast.WhileStatement, ast.ForStatement)):
            result.update(_future_declarations(statement.body, known))
    return result


def _frame_local_names(block: ast.Block) -> tuple[str, ...]:
    names: list[str] = []
    for statement in block.statements:
        if isinstance(statement, ast.VariableDeclaration):
            names.append(statement.name)
        elif isinstance(statement, ast.SelectStatement):
            for arm in statement.arms:
                names.extend(_frame_local_names(arm.body))
        elif isinstance(statement, ast.SwitchStatement):
            for case in statement.cases:
                names.extend(_frame_local_names(case.body))
        elif isinstance(statement, (ast.WhileStatement, ast.ForStatement)):
            names.extend(_frame_local_names(statement.body))
    return tuple(names)


def _contains_control_flow(block: ast.Block) -> bool:
    return any(isinstance(statement, (ast.SwitchStatement, ast.WhileStatement, ast.ForStatement, ast.BreakStatement, ast.ContinueStatement, ast.CompoundAssignmentStatement)) for statement in block.statements)


def _block_has_await(block: ast.Block, await_by_offset: Mapping[int, AsyncAwaitMarker]) -> bool:
    for statement in block.statements:
        expressions: tuple[ast.Expression, ...] = ()
        if isinstance(statement, ast.VariableDeclaration) and not isinstance(statement.initializer, ast.ArrayLiteral):
            expressions = (statement.initializer,)
        elif isinstance(statement, ast.AssignmentStatement) and not isinstance(statement.value, ast.ArrayLiteral):
            expressions = (statement.value,)
        elif isinstance(statement, (ast.ReturnStatement, ast.DiscardStatement)):
            expressions = (statement.expression,)
        elif isinstance(statement, ast.SelectStatement):
            if any(
                _tree_contains_offset(arm.operation, await_by_offset)
                or _block_has_await(arm.body, await_by_offset)
                for arm in statement.arms
            ):
                return True
        if any(_tree_contains_offset(expression, await_by_offset) for expression in expressions):
            return True
    return False


def _tree_contains_offset(expression: ast.Expression, offsets: Mapping[int, object]) -> bool:
    if expression.location.offset in offsets:
        return True
    return any(_tree_contains_offset(child, offsets) for child in _children(expression))


def _children(expression: ast.Expression) -> tuple[ast.Expression, ...]:
    if isinstance(expression, ast.CallExpression):
        return tuple(argument.expression for argument in expression.arguments)
    if isinstance(expression, ast.UnaryExpression):
        return (expression.operand,)
    if isinstance(expression, ast.BinaryExpression):
        return (expression.left, expression.right)
    if isinstance(expression, ast.IndexExpression):
        return (expression.target, expression.index)
    if isinstance(expression, ast.SliceExpression):
        return (expression.target, expression.start, expression.end)
    if isinstance(expression, ast.FieldAccessExpression):
        return (expression.target,)
    if isinstance(expression, (ast.AddressOfExpression, ast.DereferenceExpression)):
        return (expression.operand,)
    return ()


def _require_future_live(name: str, state: Mapping[str, str], location: SourceLocation) -> None:
    if state.get(name) != "live":
        raise SemanticError(f"Future '{name}' was already moved or consumed", location, diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM)


def _bind_async_functions(program: ast.Program, syntax: AsyncLanguageSyntax) -> None:
    by_name = {function.name: function for function in program.functions}
    seen: set[str] = set()
    for marker in syntax.functions:
        if marker.name in seen:
            raise SemanticError(f"duplicate async function marker for '{marker.name}'", marker.keyword_location)
        seen.add(marker.name)
        function = by_name.get(marker.name)
        if function is None or function.location.offset != marker.parsed_function_offset:
            raise SemanticError(f"async marker is not attached to function '{marker.name}'", marker.keyword_location)


def _matching_greater(tokens: tuple[Token, ...], opening: int) -> int:
    depth = 0
    for index in range(opening, len(tokens)):
        if tokens[index].kind is TokenKind.LESS:
            depth += 1
        elif tokens[index].kind is TokenKind.GREATER:
            depth -= 1
            if depth == 0:
                return index
    raise ParseError("unterminated Future<T> type", tokens[opening].location)


def _validated_spans(spans: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    ordered = tuple(sorted(set(spans)))
    previous_end = -1
    for start, end in ordered:
        if start < 0 or end <= start or start < previous_end:
            raise ParseError("contextual async/Future syntax spans overlap", SourceLocation(max(start, 0), 1, 1))
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


def _at(tokens: tuple[Token, ...], index: int) -> Token:
    if index < 0 or index >= len(tokens):
        return tokens[-1]
    return tokens[index]


def _type_key(type_name: ast.DeclaredType) -> str:
    if isinstance(type_name, ast.TypeName):
        return type_name.value
    if isinstance(type_name, ast.TypeParameterType):
        return type_name.name
    if isinstance(type_name, ast.NominalType):
        suffix = "" if not type_name.type_arguments else "<" + ",".join(_type_key(item) for item in type_name.type_arguments) + ">"
        return type_name.name + suffix
    if isinstance(type_name, ast.ArrayType):
        return f"{_type_key(type_name.element_type)}[{type_name.length}]"
    if isinstance(type_name, ast.ReferenceType):
        return f"&{'mut ' if type_name.mutable else ''}{_type_key(type_name.target)}"
    if isinstance(type_name, ast.SliceType):
        return f"&{'mut ' if type_name.mutable else ''}[{type_name.element_type.value}]"
    raise TypeError(f"unsupported async type identity {type_name!r}")


def _source_items(sources: SourceCollection) -> tuple[tuple[str, str], ...]:
    raw = sources.items() if isinstance(sources, Mapping) else sources
    result: dict[str, str] = {}
    for path, source in raw:
        normalized = normalize_logical_path(path)
        if normalized in result:
            raise SemanticError(f"duplicate source unit path '{normalized}'", diagnostic_code=DiagnosticCode.MODULE_DUPLICATE)
        result[normalized] = source
    return tuple(sorted(result.items()))


def _module_from_path(path: str) -> str:
    stem = path.rsplit(".", 1)[0]
    return stem.replace("/", ".").replace("\\", ".")


def _internal_function_name(module: ModuleId, name: str, entry_module: ModuleId) -> str:
    if module == entry_module and name == "main":
        return "main"
    return f"__s3mod_{'_'.join(module.parts)}__{name}"
